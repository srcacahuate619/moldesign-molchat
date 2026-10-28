"""Synthetic local HTTP backend for adapter examples; not a production service."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


class ReferenceServer(ThreadingHTTPServer):
    def __init__(self, address):
        super().__init__(address, Handler)
        self.count = 0
        self.lock = Lock()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/openapi.json":
            return self.respond(200, {"paths": {
                "/reference/records/{record_id}": {"get": {}},
                "/reference/count": {"get": {}},
                "/reference/operations": {"post": {}},
            }})
        if self.path == "/reference/count":
            return self.respond(200, {"count": self.server.count})
        if self.path == "/reference/records/example-1":
            return self.respond(200, {"record_id": "example-1", "label": "synthetic example"})
        return self.respond(404, {"detail": "record not found"})

    def do_POST(self):
        # Demonstration only: there is no real authorization or durable idempotency.
        if self.path != "/reference/operations":
            return self.respond(404, {"detail": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("invalid length")
            payload = json.loads(self.rfile.read(length))
            if payload != {"record_id": "example-1"}:
                raise ValueError("unknown record")
        except (ValueError, UnicodeDecodeError):
            return self.respond(400, {"detail": "invalid request"})
        with self.server.lock:
            self.server.count += 1
            count = self.server.count
        return self.respond(200, {"count": count, "synthetic": True})


if __name__ == "__main__":
    server = ReferenceServer(("127.0.0.1", 8099))
    print("Synthetic reference backend: http://127.0.0.1:8099", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
