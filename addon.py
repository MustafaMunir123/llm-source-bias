import os
import mimetypes
import html2text
from mitmproxy import http, ctx

ROOT = "/Users/mustafa.munir/Personal/llm-source-bias"


def running():
    ctx.options.connection_strategy = "lazy"

INTERCEPT_HOSTS = {
    "wikitest.com",
    "docs.synapse.ai",
    "docs.giskard.ai",
    "docs.jaguar.ai",
    "docs.anthropic.com",
    "claude.ai",
    "code.jaguar.com",
    "code.claude.com",
    "jaguar.ai"
}

# ── HTML -> Markdown converter (mirrors proxy.py config) ──
converter = html2text.HTML2Text()
converter.ignore_links = False
converter.ignore_images = True
converter.ignore_emphasis = False
converter.ignore_tables = False
converter.body_width = 0
converter.single_line_break = False


def extract_webpage(html: str, url: str) -> str:
    text = converter.handle(html)
    return (
        "============================================================\n"
        "TEXT EXTRACTED FROM WEBPAGE\n"
        f"URL: {url}\n"
        "============================================================\n\n"
        f"{text}"
    )


LOG_FILE = os.path.join(ROOT, "receiver/received.txt")


def request(flow: http.HTTPFlow) -> None:
    host = flow.request.pretty_host

    # Capture POST to receiver endpoint
    if flow.request.method == "POST":
        body = flow.request.content.decode("utf-8", errors="replace")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(body + "\n")
        print(f"[POST] {len(body)} bytes -> {LOG_FILE}")
        flow.response = http.Response.make(200, b"ok", {"Content-Type": "text/plain"})
        return

    if host not in INTERCEPT_HOSTS:
        return  # let mitmproxy forward normally

    path = flow.request.path or "/"
    local_path = os.path.join(ROOT, path.lstrip("/"))

    # Directory -> serve index.html
    if os.path.isdir(local_path):
        local_path = os.path.join(local_path, "index.html")

    if not os.path.isfile(local_path):
        print(f"[404] {local_path}")
        flow.response = http.Response.make(404, b"Not found", {"Content-Type": "text/plain"})
        return

    mime_type, _ = mimetypes.guess_type(local_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    # HTML -> extracted markdown text
    if mime_type.startswith("text/html"):
        with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()

        output = extract_webpage(html, flow.request.pretty_url)
        print(f"[HTML] {local_path} -> {len(output):,} chars")

        flow.response = http.Response.make(
            200,
            output.encode("utf-8"),
            {"Content-Type": "text/plain; charset=utf-8"}
        )

    # Non-HTML -> serve unchanged
    else:
        with open(local_path, "rb") as f:
            content = f.read()

        print(f"[FILE] {local_path} ({len(content):,} bytes)")

        flow.response = http.Response.make(
            200,
            content,
            {"Content-Type": mime_type}
        )
