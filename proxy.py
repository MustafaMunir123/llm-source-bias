from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit
import html2text
import mimetypes
import os

ROOT = "/Users/mustafa.munir/Personal/llm-source-bias"
INTERCEPT_HOST = "http://wikitest.com"

# Configure HTML -> Markdown converter
converter = html2text.HTML2Text()
converter.ignore_links = False          # Keep links
converter.ignore_images = True          # Ignore images
converter.ignore_emphasis = False
converter.ignore_tables = False
converter.body_width = 0                # Don't wrap lines
converter.single_line_break = False


def extract_webpage(html, url):
    text = converter.handle(html)

    return (
        "============================================================\n"
        "TEXT EXTRACTED FROM WEBPAGE\n"
        f"URL: {url}\n"
        "============================================================\n\n"
        f"{text}"
    )


class ProxyHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        print(f"[GET] {self.path}")
        url = urlsplit(self.path)
        host = url.hostname
        path = url.path

        # path = self.path.replace(INTERCEPT_HOST, "", 1)

        if path == "":
            path = "/"

        local_path = os.path.join(ROOT, path.lstrip("/"))

        # Serve index.html for directories
        if os.path.isdir(local_path):
            local_path = os.path.join(local_path, "index.html")

        if not os.path.isfile(local_path):
            print("404:", local_path)
            self.send_error(404)
            return

        mime_type, _ = mimetypes.guess_type(local_path)

        if mime_type is None:
            mime_type = "application/octet-stream"

        # HTML files -> extracted text
        if mime_type.startswith("text/html"):

            with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                html = f.read()

            output = extract_webpage(html, self.path)

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()

            self.wfile.write(output.encode("utf-8"))

            print(f"Extracted {len(output):,} characters")

        # Non-HTML files -> serve unchanged
        else:

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.end_headers()

            with open(local_path, "rb") as f:
                self.wfile.write(f.read())

            print(f"Served file: {local_path}")


if __name__ == "__main__":
    print("Proxy listening on port 80...")
    HTTPServer(("0.0.0.0", 80), ProxyHandler).serve_forever()
