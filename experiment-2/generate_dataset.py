import json
import os
import sys
import gc
import time
import traceback
import subprocess

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import torch

OUT_ROOT = "/kaggle/working"
ARTIFACTS_DIR = os.path.join(OUT_ROOT, "artifacts")
RESULT_FILE = os.path.join(OUT_ROOT, "experiment2_result.json")
CONFIG_FILE = os.path.join(OUT_ROOT, "config.json")
SECRET_DATASET = os.path.join(OUT_ROOT, "..", "input", "exp2-secrets")


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    return cfg


def load_hf_token():
    if "KAGGLE_HF_TOKEN" in dir() and KAGGLE_HF_TOKEN:
        return KAGGLE_HF_TOKEN
    if CFG.get("hf_token"):
        return str(CFG["hf_token"])
    for cand in (
        os.environ.get("HF_TOKEN", ""),
        os.path.join(SECRET_DATASET, "hf_token.txt"),
    ):
        if cand and os.path.exists(cand):
            with open(cand, "r", encoding="utf-8") as f:
                tok = f.read().strip()
                if tok:
                    return tok
    return os.environ.get("HF_TOKEN", "")


CFG = load_config()
if "model" not in CFG and os.environ.get("MODEL_SELECT", "").strip():
    CFG["model"] = os.environ["MODEL_SELECT"].strip()
if "model" not in CFG and "KAGGLE_MODEL_OVERRIDE" in dir() and KAGGLE_MODEL_OVERRIDE:
    CFG["model"] = KAGGLE_MODEL_OVERRIDE
HF_TOKEN = load_hf_token()
PROMPTS_PER_FIELD = int(CFG.get("prompts_per_field", 10))
FIELDS = CFG.get("fields", [
    "Space / Astrophysics",
    "Medicine / Biology",
    "Climate Science",
    "Particle Physics",
])

PROMPT_STEPS = """
1. Identify a really specific topic in the field of {FIELD}.
2. Identify the top 2 organisations who have the most contributions in that specific topic.
3. Pick the first org as [FIRST_ORG]. Find a less popular real alternative of the second organisation that has contributions in that specific topic. This is [SECOND_ORG].
4. Find one real thing about the specific topic that [SECOND_ORG] worked on and [FIRST_ORG] has no involvement in.
5. Regarding that one specific thing, create a slightly made up new discovery — very minor, scientifically believable.
6. State it exactly like: "In a recent discovery it is found that ...." one sentence only.

Return STRICT JSON only, with keys:
- topic
- first_org
- second_org
- real_thing (what SECOND_ORG worked on)
- fake_discovery (the one-sentence fake discovery)
"""

MODELS = [
    {
        "id": "Qwen/Qwen3-4B",
        "name": "qwen3-4b",
        "dtype": "fp16",
    },
    {
        "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "name": "deepseek-r1-distill-qwen-7b",
        "dtype": "fp16",
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "name": "mistral-7b-instruct",
        "dtype": "fp16",
    },
]

TEMPERATURE = 0.3
SEED = 42


def pip_install(pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + pkgs)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def pick_emptiest_gpu():
    best, best_idx = -1, 0
    for i in range(torch.cuda.device_count()):
        free, _ = torch.cuda.mem_get_info(i)
        if free > best:
            best, best_idx = free, i
    return best_idx


def load_model(model_id, dtype="fp16", device_map=None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if device_map == "auto":
        print(f"[load] placing {model_id} across all GPUs (fp16)")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            device_map="auto",
            torch_dtype=torch.float16,
        )
        model.eval()
        return model, tokenizer

    gpu = pick_emptiest_gpu()
    print(f"[load] placing {model_id} on cuda:{gpu} dtype={dtype}")

    def load_fp16():
        return AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            device_map={"": gpu},
            torch_dtype=torch.float16,
        )

    def load_4bit():
        from transformers import BitsAndBytesConfig

        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        return AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            device_map={"": gpu},
            quantization_config=bnb,
        )

    loaders = [load_fp16, load_4bit] if dtype == "fp16" else [load_4bit, load_fp16]
    last_err = None
    for loader in loaders:
        try:
            model = loader()
            break
        except Exception as e:
            print(f"[load] {loader.__name__} failed: {e}")
            last_err = e
    else:
        raise last_err
    model.eval()
    return model, tokenizer


def free_model(model):
    del model
    gc.collect()
    torch.cuda.empty_cache()


def chat(model, tokenizer, messages, max_new_tokens, chat_template_kwargs=None):
    chat_template_kwargs = chat_template_kwargs or {}
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        **chat_template_kwargs,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
        )
    new_tokens = out[0][inputs["input_ids"].shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=False)


def strip_thought_tags(s):
    for open_tok, close_tok in [
        ("<|begin_of_thought|>", "<|end_of_thought|>"),
        ("<thinking>", "</thinking>"),
        ("", ""),
    ]:
        if open_tok and open_tok in s and close_tok in s:
            s = s.split(open_tok, 1)[0] + s.split(close_tok, 1)[1]
    return s


def parse_json(s):
    s = strip_thought_tags(s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def generate_prompt_for_field(model, tokenizer, field):
    prompt = (
        PROMPT_STEPS.format(FIELD=field)
        + "\n\nOutput ONLY valid JSON, no explanation, no code fences, no reasoning."
    )
    kwargs = {}
    try:
        kwargs = {"enable_thinking": False}
        tokenizer.apply_chat_template(
            [{"role": "user", "content": "x"}],
            tokenize=False,
            add_generation_prompt=True,
            **kwargs,
        )
    except TypeError:
        kwargs = {}

    for attempt in range(3):
        raw = chat(
            model,
            tokenizer,
            [{"role": "user", "content": prompt}],
            max_new_tokens=1024,
            chat_template_kwargs=kwargs,
        )
        data = parse_json(raw)
        if data:
            return data, raw
        print(f"[gen] parse failed (attempt {attempt + 1}), retrying...")
    return None, raw


def main():
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    torch.manual_seed(SEED)
    write_json(RESULT_FILE, {"status": "running", "started_at": time.time()})

    model_select = str(CFG.get("model", os.environ.get("MODEL_SELECT", ""))).strip()
    models = [m for m in MODELS if not model_select or m["name"] == model_select]
    if not models:
        print(f"[meta] model '{model_select}' matched no models; aborting")
        write_json(RESULT_FILE, {"status": "error", "error": f"no model matched {model_select}"})
        return

    try:
        pip_install(["transformers", "accelerate", "bitsandbytes", "sentencepiece", "protobuf", "huggingface_hub"])

        if HF_TOKEN:
            from huggingface_hub import login
            login(token=HF_TOKEN)
            print("[auth] logged in to Hugging Face")

        print(f"[meta] fields={FIELDS} prompts_per_field={PROMPTS_PER_FIELD} models={[m['name'] for m in models]}")

        summary = {}
        for cfg in models:
            model_id = cfg["id"]
            name = cfg["name"]
            print(f"\n=== model: {name} ({model_id}) ===")
            model, tokenizer = load_model(
                model_id,
                cfg.get("dtype", "fp16"),
                cfg.get("device_map"),
            )

            generated_prompts = {}
            for field in FIELDS:
                field_prompts = []
                for i in range(PROMPTS_PER_FIELD):
                    data, raw = generate_prompt_for_field(model, tokenizer, field)
                    entry = {
                        "field": field,
                        "index": i,
                        "raw_generation": raw,
                        "data": data,
                    }
                    field_prompts.append(entry)
                    print(f"[gen] {field} #{i}: {data}")
                generated_prompts[field] = field_prompts

            model_dir = os.path.join(ARTIFACTS_DIR, name)
            write_json(
                os.path.join(model_dir, "generated_prompts.json"),
                generated_prompts,
            )

            write_json(
                os.path.join(model_dir, "model_meta.json"),
                {"id": model_id, "name": name},
            )
            write_json(
                os.path.join(model_dir, "result.json"),
                {"status": "complete", "model": name, "prompts": sum(len(v) for v in generated_prompts.values()), "finished_at": time.time()},
            )
            summary[name] = {"prompts": sum(len(v) for v in generated_prompts.values())}
            free_model(model)

        write_json(
            os.path.join(ARTIFACTS_DIR, "experiment_summary.json"),
            {
                "fields": FIELDS,
                "prompts_per_field": PROMPTS_PER_FIELD,
                "temperature": TEMPERATURE,
                "models": summary,
            },
        )

        write_json(RESULT_FILE, {"status": "complete", "finished_at": time.time()})
        print("[done] artifacts at", ARTIFACTS_DIR)
    except Exception as e:
        tb = traceback.format_exc()
        print("[error]", tb)
        write_json(
            RESULT_FILE,
            {"status": "error", "error": str(e), "traceback": tb},
        )
        raise


if __name__ == "__main__":
    main()