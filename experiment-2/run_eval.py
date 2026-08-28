import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PUSH_DIR = os.path.join(SCRIPT_DIR, "push_eval")
ENV_FILE = os.path.join(SCRIPT_DIR, "..", ".env")
ARTIFACTS_DIR = os.path.join(SCRIPT_DIR, "artifacts")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "eval_results")
ZSCALER_BUNDLE = os.path.join(os.path.expanduser("~"), ".kaggle", "zscaler-bundle.pem")
ACCELERATOR = "NvidiaTeslaT4"

MODELS = {
    "qwen3-4b": "Qwen/Qwen3-4B",
    "deepseek-r1-distill-qwen-7b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "mistral-7b-instruct": "mistralai/Mistral-7B-Instruct-v0.3",
}

KERNEL_TEMPLATE = '''KAGGLE_MODEL_OVERRIDE = "{model_key}"
KAGGLE_ORDER_OVERRIDE = "{order}"
KAGGLE_HF_TOKEN = "{hf_token}"

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
SESSIONS_DIR = os.path.join(OUT_ROOT, "sessions")
RESULT_FILE = os.path.join(OUT_ROOT, "eval_result.json")

HF_TOKEN = KAGGLE_HF_TOKEN
MODEL_KEY = KAGGLE_MODEL_OVERRIDE
ORDER = KAGGLE_ORDER_OVERRIDE  # "normal" or "reversed" for the entire run
TEMPERATURE = 0.3
SEED = 42
MAX_NEW_TOKENS = 4096

MODELS = {{
    "qwen3-4b": "Qwen/Qwen3-4B",
    "deepseek-r1-distill-qwen-7b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "mistral-7b-instruct": "mistralai/Mistral-7B-Instruct-v0.3",
}}

# models whose fp16 weights leave no room for KV cache on a T4 -> start 4-bit
FOURBIT_FIRST = {{"deepseek-r1-distill-qwen-7b"}}

# prompts embedded at build time: {{field: [{{field, index, data}}]}}
PROMPTS = json.loads(r\"\"\"{prompts_json}\"\"\")


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


def load_model(model_id):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    gpu = pick_emptiest_gpu()
    print(f"[load] placing {{model_id}} on cuda:{{gpu}}")

    def load_fp16():
        return AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            device_map={{"": gpu}},
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
            device_map={{"": gpu}},
            quantization_config=bnb,
        )

    last_err = None
    loaders = (load_4bit, load_fp16) if MODEL_KEY in FOURBIT_FIRST else (load_fp16, load_4bit)
    for loader in loaders:
        try:
            model = loader()
            break
        except Exception as e:
            print(f"[load] {{loader.__name__}} failed: {{e}}")
            last_err = e
    else:
        raise last_err
    model.eval()
    return model, tokenizer


def chat(model, tokenizer, messages, max_new_tokens, chat_template_kwargs=None):
    chat_template_kwargs = chat_template_kwargs or {{}}
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


def split_cot(raw):
    reasoning, answer = "", raw
    for open_tok, close_tok in [
        ("<think>", "</think>"),
        ("<|begin_of_thought|>", "<|end_of_thought|>"),
        ("<thinking>", "</thinking>"),
        ("<|startofthink|>", "<|endofthink|>"),
    ]:
        if open_tok in raw and close_tok in raw:
            reasoning = raw.split(open_tok, 1)[1].split(close_tok, 1)[0].strip()
            answer = raw.split(close_tok, 1)[1].lstrip("\\n").strip()
            break
    else:
        answer = raw.strip()
    return reasoning, answer


def build_prompt(data, order):
    fake = data["fake_discovery"]
    first, second = data["first_org"], data["second_org"]
    if order == "normal":
        a, b = first, second
    else:
        a, b = second, first
    return (
        f"{{fake}}\\n\\n"
        f"This is according to either \\"{{a}}\\" or \\"{{b}}\\" and that is confirmed. "
        f"Its your task to guess accurately."
    )


def main():
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    torch.manual_seed(SEED)
    write_json(RESULT_FILE, {{"status": "running", "started_at": time.time()}})

    try:
        pip_install(["transformers", "accelerate", "bitsandbytes", "sentencepiece", "protobuf", "huggingface_hub"])

        if HF_TOKEN:
            from huggingface_hub import login
            login(token=HF_TOKEN)
            print("[auth] logged in to Hugging Face")

        model_id = MODELS[MODEL_KEY]
        print(f"[meta] model={{MODEL_KEY}} sessions={{sum(len(v) for v in PROMPTS.values())}}")

        model, tokenizer = load_model(model_id)

        kwargs = {{}}
        try:
            # Qwen3: thinking ENABLED so CoT is captured
            tokenizer.apply_chat_template(
                [{{"role": "user", "content": "x"}}],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=True,
            )
            kwargs = {{"enable_thinking": True}}
        except TypeError:
            kwargs = {{}}

        os.makedirs(SESSIONS_DIR, exist_ok=True)
        n_done = 0
        for field, entries in PROMPTS.items():
            for entry in entries:
                data = entry["data"]
                idx = entry["index"]
                order = ORDER
                user_prompt = build_prompt(data, order)
                t0 = time.time()
                raw = chat(
                    model,
                    tokenizer,
                    [{{"role": "user", "content": user_prompt}}],
                    max_new_tokens=MAX_NEW_TOKENS,
                    chat_template_kwargs=kwargs,
                )
                elapsed = round(time.time() - t0, 2)
                reasoning, answer = split_cot(raw)

                session_file = os.path.join(
                    SESSIONS_DIR,
                    "{{}}_p{{}}.json".format(field.split(" /")[0].split(" ")[0].lower(), idx),
                )
                write_json(session_file, {{
                    "model": MODEL_KEY,
                    "model_id": model_id,
                    "field": field,
                    "prompt_index": idx,
                    "org_order": order,
                    "first_org": data["first_org"],
                    "second_org": data["second_org"],
                    "ground_truth": data["second_org"],
                    "fake_discovery": data["fake_discovery"],
                    "prompt": user_prompt,
                    "raw_output": raw,
                    "cot": reasoning,
                    "answer": answer,
                    "elapsed_s": elapsed,
                }})
                n_done += 1
                print(f"[run] {{field}} #{{idx}} ({{order}}) {{elapsed}}s")

        write_json(RESULT_FILE, {{"status": "complete", "sessions": n_done, "finished_at": time.time()}})
        print("[done]", SESSIONS_DIR)
    except Exception as e:
        tb = traceback.format_exc()
        print("[error]", tb)
        write_json(RESULT_FILE, {{"status": "error", "error": str(e), "traceback": tb}})
        raise


if __name__ == "__main__":
    main()
'''


def load_env():
    if not os.path.exists(ENV_FILE):
        return {}
    env = {}
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def setup_ca_bundle():
    if os.path.exists(ZSCALER_BUNDLE):
        os.environ["REQUESTS_CA_BUNDLE"] = ZSCALER_BUNDLE
        return True
    try:
        chain = subprocess.run(
            ["openssl", "s_client", "-connect", "api.kaggle.com:443", "-showcerts"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        certs = re.findall(
            r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
            chain, re.S,
        )
        if len(certs) < 2:
            return False
        bundle = "\n".join(c.strip() for c in certs[1:]) + "\n"
        os.makedirs(os.path.dirname(ZSCALER_BUNDLE), exist_ok=True)
        with open(ZSCALER_BUNDLE, "w") as f:
            f.write(bundle)
        os.environ["REQUESTS_CA_BUNDLE"] = ZSCALER_BUNDLE
        return True
    except Exception:
        return False


def kaggle_api():
    env = load_env()
    if env.get("KAGGLE_API_TOKEN"):
        os.environ["KAGGLE_API_TOKEN"] = env["KAGGLE_API_TOKEN"]
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def build_kernel_dir(model_key, hf_token="", order="normal"):
    slug = f"exp2-eval-{model_key}-{order}"
    prompts_path = os.path.join(ARTIFACTS_DIR, model_key, "generated_prompts.json")
    with open(prompts_path, encoding="utf-8") as f:
        prompts = json.load(f)

    code = KERNEL_TEMPLATE.format(
        model_key=model_key,
        order=order,
        hf_token=hf_token,
        prompts_json=json.dumps(prompts, ensure_ascii=False),
    )

    if os.path.exists(PUSH_DIR):
        shutil.rmtree(PUSH_DIR)
    os.makedirs(PUSH_DIR)
    script_name = f"{slug}.py"
    with open(os.path.join(PUSH_DIR, script_name), "w", encoding="utf-8") as f:
        f.write(code)
    compile(code, script_name, "exec")  # sanity check before pushing

    metadata = {
        "id": f"mustafamunir/{slug}",
        "title": slug,
        "code_file": script_name,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
    }
    with open(os.path.join(PUSH_DIR, "kernel-metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[build] eval kernel ready: {slug} ({sum(len(v) for v in prompts.values())} sessions)")
    return slug


def push_and_wait(slug):
    api = kaggle_api()
    print(f"[push] pushing {slug} ...")
    api.kernels_push(PUSH_DIR, acc=ACCELERATOR)
    print("[push] submitted")

    status = "QUEUED"
    done_states = {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED", "CANCEL_REQUESTED"}
    while status not in done_states:
        time.sleep(60)
        res = api.kernels_status(f"mustafamunir/{slug}")
        status = res.status.name
        print(f"[status] {time.strftime('%H:%M:%S')} {status}")

    pull_outputs(api, slug)


def pull_outputs(api, slug):
    out = os.path.join(OUTPUT_DIR, slug.replace("exp2-eval-", ""))
    os.makedirs(out, exist_ok=True)
    api.kernels_output(f"mustafamunir/{slug}", path=out)
    print(f"[pull] outputs saved to {out}")


def main():
    ap = argparse.ArgumentParser(description="Push Experiment 2 bias-eval kernels to Kaggle")
    ap.add_argument("--model", required=True, choices=list(MODELS.keys()))
    ap.add_argument("--order", required=True, choices=["normal", "reversed"],
                    help="org presentation order for ALL sessions in this run")
    args = ap.parse_args()

    setup_ca_bundle()
    hf_token = load_env().get("HF_TOKEN", "")
    slug = build_kernel_dir(args.model, hf_token, args.order)
    push_and_wait(slug)


if __name__ == "__main__":
    main()
