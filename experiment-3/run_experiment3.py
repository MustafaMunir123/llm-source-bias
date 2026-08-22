import argparse
import base64
import io
import json
import os
import ssl
import sys
import time
import uuid
import zipfile
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from websocket import create_connection

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REMOTE_SCRIPT = os.path.join(SCRIPT_DIR, "generate_dataset.py")
RESULT_NAME = "experiment3_result.json"
BUNDLE_NAME = "experiment3_bundle.zip"
ENV_FILE = os.path.join(SCRIPT_DIR, "..", ".env")


def load_env(path=ENV_FILE):
    if not os.path.exists(path):
        return {}
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def parse_proxy_url(url):
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    token = parse_qs(parsed.query).get("token", [None])[0]
    if token:
        base = f"{parsed.scheme}://{parsed.netloc}"
        return base, token
    path = parsed.path.rstrip("/")
    base = f"{parsed.scheme}://{parsed.netloc}{path}"
    return base, None


def make_session():
    s = requests.Session()
    s.verify = False
    retry = Retry(total=5, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def build_bundle(remote_code: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("generate_dataset.py", remote_code)
    return buf.getvalue()


def upload_bundle(session, base, bundle_bytes):
    b64 = base64.b64encode(bundle_bytes).decode()
    url = f"{base}/api/contents/{BUNDLE_NAME}"
    r = session.put(
        url,
        json={"type": "file", "format": "base64", "content": b64},
        timeout=60,
    )
    r.raise_for_status()
    print(f"[upload] {BUNDLE_NAME} ({len(bundle_bytes)} bytes)")


def delete_stale(session, base, name):
    try:
        session.delete(f"{base}/api/contents/{name}", timeout=30)
    except Exception:
        pass


def start_kernel(session, base):
    r = session.post(f"{base}/api/kernels", json={"name": "python3"}, timeout=60)
    r.raise_for_status()
    kernel_id = r.json()["id"]
    print(f"[kernel] started {kernel_id}")
    return kernel_id


def ws_url(base, kernel_id):
    scheme = "wss" if base.startswith("https") else "ws"
    return f"{scheme}://{base.split('://', 1)[1]}/api/kernels/{kernel_id}/channels"


def build_execute_request(code):
    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"
    msg_id = uuid.uuid4().hex
    return {
        "header": {
            "msg_id": msg_id,
            "username": "",
            "session": uuid.uuid4().hex,
            "date": now,
            "msg_type": "execute_request",
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "content": {
            "code": code,
            "silent": False,
            "store_history": True,
            "user_expressions": {},
            "allow_stdin": False,
            "stop_on_error": True,
        },
        "buffers": [],
        "channel": "shell",
    }


def remote_code_for_bundle(env=None):
    env = env or {}
    env_lines = "".join(
        f'os.environ.setdefault({json.dumps(k)}, {json.dumps(v)})\n'
        for k, v in env.items()
    )
    return f"""
import zipfile, os, sys
{env_lines}
with zipfile.ZipFile("/kaggle/working/{BUNDLE_NAME}") as z:
    z.extractall("/kaggle/working/experiment3_src")
sys.path.insert(0, "/kaggle/working/experiment3_src")
import generate_dataset
generate_dataset.main()
print("EXPERIMENT3_RUNNER_DONE")
"""


def run_and_wait(base, kernel_id, env=None):
    sslopt = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
    ws = create_connection(ws_url(base, kernel_id), sslopt=sslopt, timeout=60)
    code = remote_code_for_bundle(env)
    req = build_execute_request(code)
    ws.send(json.dumps(req))
    msg_id = req["header"]["msg_id"]

    print("[ws] waiting for execute_reply (run can take a while)...")
    while True:
        raw = ws.recv()
        if not raw:
            continue
        msg = json.loads(raw)
        parent = msg.get("parent_header", {}).get("msg_id")
        if parent != msg_id:
            continue
        msg_type = msg.get("msg_type")
        if msg_type == "stream":
            print(msg.get("content", {}).get("text", ""), end="")
        elif msg_type == "execute_reply":
            status = msg.get("content", {}).get("status")
            print(f"\n[ws] execute_reply status={status}")
            return status


def wait_for_result(session, base, timeout_min=45):
    url = f"{base}/api/contents/{RESULT_NAME}"
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                content = r.json().get("content", "")
                data = json.loads(base64.b64decode(content).decode())
                print(f"[result] status={data.get('status')}")
                return data
        except requests.exceptions.ReadTimeout:
            print("[poll] ReadTimeout — JWT may have expired; retrying...")
        except Exception as e:
            print(f"[poll] {e}")
        time.sleep(15)
    return None


def download_dir(session, base, remote_dir, local_dir):
    url = f"{base}/api/contents/{remote_dir}"
    r = session.get(url, timeout=30)
    r.raise_for_status()
    listing = r.json()
    if listing.get("type") == "directory":
        for item in listing.get("content", []):
            child_path = item["path"]
            if item["type"] == "directory":
                download_dir(session, base, child_path, os.path.join(local_dir, item["name"]))
            else:
                download_file(session, base, child_path, os.path.join(local_dir, item["name"]))
    else:
        download_file(session, base, remote_dir, local_dir)


def download_file(session, base, remote_path, local_path):
    url = f"{base}/api/contents/{remote_path}?content=1"
    r = session.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(data.get("content", ""))


def main():
    ap = argparse.ArgumentParser(description="Run Experiment 3 on Kaggle T4x2 via VSCode-compatible URL")
    ap.add_argument("url", help="VSCode-compatible Jupyter proxy URL from the open Kaggle notebook")
    ap.add_argument("--timeout-min", type=int, default=45, help="max minutes to wait for completion")
    ap.add_argument("--out", default=os.path.join(SCRIPT_DIR, "artifacts"), help="local output dir")
    ap.add_argument("--model", default="", help="run only this model (name from generate_dataset.py), e.g. qwen3-4b")
    args = ap.parse_args()

    base, token = parse_proxy_url(args.url)
    print(f"[proxy] base={base} auth={'token' if token else 'jwt-in-path'}")

    session = make_session()

    with open(REMOTE_SCRIPT, "r", encoding="utf-8") as f:
        remote_code = f.read()
    bundle = build_bundle(remote_code)

    env = load_env()
    remote_env = {
        k: v
        for k, v in env.items()
        if k in ("HF_TOKEN", "KAGGLE_USERNAME", "KAGGLE_API_KEY")
    }
    if args.model:
        remote_env["MODEL_SELECT"] = args.model
    for k, v in remote_env.items():
        print(f"[env] passing {k} (len={len(v)})")

    delete_stale(session, base, RESULT_NAME)
    upload_bundle(session, base, bundle)
    kernel_id = start_kernel(session, base)

    status = run_and_wait(base, kernel_id, env=remote_env)
    if status != "ok":
        print("[run] execute_reply was not ok — check remote logs above")

    result = wait_for_result(session, base, timeout_min=args.timeout_min)
    if result is None:
        print("[poll] no result file within timeout — session JWT likely expired; kernel may still be running")
        return 1

    local = args.out
    download_dir(session, base, "artifacts", local)
    print(f"[done] artifacts downloaded to {local}")
    return 0


if __name__ == "__main__":
    sys.exit(main())