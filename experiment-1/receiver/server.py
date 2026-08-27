from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8765
LOG_FILE = "receiver/received.txt"


class Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(body + "\n")

        print(f"[RECEIVED] {len(body)} bytes -> {LOG_FILE}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass  # suppress default request logs


if __name__ == "__main__":
    print(f"Receiver listening on port {PORT}...")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
