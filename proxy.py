from http.server import BaseHTTPRequestHandler, HTTPServer
import os

ROOT = "/Users/mustafa.munir/"

class ProxyHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        print("Proxy request:", self.path)

        # Ignore the hostname and serve local files
        path = self.path.replace("http://wikitest.com", "")
        
        if path == "":
            path = "/"

        filename = os.path.join(ROOT, path.lstrip("/"))

        if os.path.isdir(filename):
            body = "<h1>Directory</h1><ul>"
            for f in os.listdir(filename):
                body += f"<li>{f}</li>"
            body += "</ul>"

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())

        elif os.path.isfile(filename):
            self.send_response(200)
            self.end_headers()

            with open(filename, "rb") as f:
                self.wfile.write(f.read())

        else:
            self.send_error(404)


HTTPServer(("0.0.0.0", 80), ProxyHandler).serve_forever()
