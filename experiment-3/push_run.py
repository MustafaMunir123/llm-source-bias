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
PUSH_DIR = os.path.join(SCRIPT_DIR, "push")
GEN_SCRIPT = os.path.join(SCRIPT_DIR, "generate_dataset.py")
ENV_FILE = os.path.join(SCRIPT_DIR, "..", ".env")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "artifacts")
ZSCALER_BUNDLE = os.path.join(os.path.expanduser("~"), ".kaggle", "zscaler-bundle.pem")

KERNEL_SLUG = "exp3-dataset-gen"
ACCELERATOR = "NvidiaTeslaT4"

MODELS = {
    "qwen3-4b": "Qwen/Qwen3-4B",
    "deepseek-r1-distill-qwen-7b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "mistral-7b-instruct": "mistralai/Mistral-7B-Instruct-v0.3",
}


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
    """Build a CA bundle trusting the corporate TLS proxy (Zscaler) so
    requests/kaggle can verify api.kaggle.com. Detects via openssl chain."""
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
            print("[ca] could not capture proxy cert chain; using system trust")
            return False
        leaf_issuer = None
        for i, c in enumerate(certs):
            p = "/tmp/_zs_leaf.pem"
            open(p, "w").write(c)
            r = subprocess.run(["openssl", "x509", "-in", p, "-noout", "-issuer"],
                               capture_output=True, text=True).stdout
            if i == 0:
                leaf_issuer = r.strip()
        bundle = "\n".join(c.strip() for c in certs[1:]) + "\n"
        os.makedirs(os.path.dirname(ZSCALER_BUNDLE), exist_ok=True)
        with open(ZSCALER_BUNDLE, "w") as f:
            f.write(bundle)
        os.environ["REQUESTS_CA_BUNDLE"] = ZSCALER_BUNDLE
        print("[ca] saved proxy CA bundle to ~/.kaggle/zscaler-bundle.pem")
        return True
    except Exception as e:
        print(f"[ca] could not build CA bundle: {e}")
        return False


def kaggle_api():
    env = load_env()
    if env.get("KAGGLE_API_TOKEN"):
        os.environ["KAGGLE_API_TOKEN"] = env["KAGGLE_API_TOKEN"]
    elif env.get("KAGGLE_API_KEY") and env.get("KAGGLE_USERNAME"):
        os.environ["KAGGLE_USERNAME"] = env["KAGGLE_USERNAME"]
        os.environ["KAGGLE_API_KEY"] = env["KAGGLE_API_KEY"]
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def build_kernel_dir(model_key, prompts_per_field, hf_token=""):
    global KERNEL_SLUG
    KERNEL_SLUG = f"exp3-{model_key}"
    if os.path.exists(PUSH_DIR):
        shutil.rmtree(PUSH_DIR)
    os.makedirs(PUSH_DIR)

    with open(GEN_SCRIPT, "r") as f:
        code = f.read()

    inject = f'KAGGLE_MODEL_OVERRIDE = "{model_key}"\n'
    if hf_token:
        inject += f'KAGGLE_HF_TOKEN = "{hf_token}"\n'
    code = inject + code

    with open(os.path.join(PUSH_DIR, "generate_dataset.py"), "w") as f:
        f.write(code)
    config = {
        "model": model_key,
        "prompts_per_field": prompts_per_field,
    }
    if hf_token:
        config["hf_token"] = hf_token
    with open(os.path.join(PUSH_DIR, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    metadata = {
        "id": f"mustafamunir/{KERNEL_SLUG}",
        "title": KERNEL_SLUG,
        "code_file": "generate_dataset.py",
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
    print(f"[build] kernel dir ready for model={model_key} prompts={prompts_per_field}")


def push_and_wait(model_key):
    api = kaggle_api()
    print(f"[push] pushing {KERNEL_SLUG} (model={model_key}) with {ACCELERATOR} ...")
    api.kernels_push(PUSH_DIR, acc=ACCELERATOR)
    print("[push] submitted")

    status = "queued"
    done_states = {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED", "CANCEL_REQUESTED"}
    while True:
        time.sleep(60)
        res = api.kernels_status(f"mustafamunir/{KERNEL_SLUG}")
        status = res.status.name
        print(f"[status] {time.strftime('%H:%M:%S')} {status}")
        if status in done_states:
            break

    if status != "COMPLETE":
        print("[run] kernel did not complete; pulling output for logs")
    pull_outputs()


def pull_outputs():
    api = kaggle_api()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    api.kernels_output(f"mustafamunir/{KERNEL_SLUG}", path=OUTPUT_DIR)
    print(f"[pull] outputs saved to {OUTPUT_DIR}")


def main():
    ap = argparse.ArgumentParser(description="Push Experiment 3 dataset-gen kernel to Kaggle (T4)")
    ap.add_argument("--model", required=True, choices=list(MODELS.keys()),
                    help="which model to run (one push per model)")
    ap.add_argument("--prompts-per-field", type=int, default=10)
    ap.add_argument("--pull-only", action="store_true",
                    help="only download outputs from the last run, don't push")
    args = ap.parse_args()

    if not setup_ca_bundle():
        print("[warn] continuing with system trust; api.kaggle.com may fail behind proxy")

    if args.pull_only:
        pull_outputs()
        return

    env = load_env()
    hf_token = env.get("HF_TOKEN", "")
    if not hf_token:
        print("[warn] HF_TOKEN not found in .env; gated models may fail to download")

    build_kernel_dir(args.model, args.prompts_per_field, hf_token)
    push_and_wait(args.model)


if __name__ == "__main__":
    main()