"""Local stand-in for the GUS relay, for testing gus.html without AWS.

Runs the real handler.py against in-memory storage on http://localhost:8714.
Test keys: game master "test-gm", player "test-player".
Open http://localhost:8713/gus.html?relay=http://localhost:8714#gm=test-gm
"""
import hashlib
import json
import sys
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OBJECTS = {}


class NoSuchKey(Exception):
    pass


class FakeS3:
    exceptions = types.SimpleNamespace(NoSuchKey=NoSuchKey)

    def get_object(self, Bucket, Key):
        if Key not in OBJECTS:
            raise NoSuchKey(Key)
        return {"Body": types.SimpleNamespace(read=lambda: OBJECTS[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        OBJECTS[Key] = Body

    def delete_object(self, Bucket, Key):
        OBJECTS.pop(Key, None)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return "http://localhost:8714/blob/" + Params["Key"]


class FakeSSM:
    def get_parameters(self, Names, WithDecryption):
        values = {"gm": "test-gm", "player": "test-player"}
        return {"Parameters": [
            {"Name": n, "Value": hashlib.sha256(values[n.rsplit("/", 1)[1].split("-")[0]].encode()).hexdigest()}
            for n in Names]}


fake = types.ModuleType("boto3")
fake.client = lambda name, **_: FakeS3() if name == "s3" else FakeSSM()
sys.modules["boto3"] = fake
config = types.ModuleType("botocore.config")
config.Config = lambda **_: None
sys.modules["botocore"] = types.ModuleType("botocore")
sys.modules["botocore.config"] = config

import os  # noqa: E402

os.environ.setdefault("BUCKET", "local")
sys.path.insert(0, str(Path(__file__).parent))
import handler  # noqa: E402


class Relay(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-headers", "content-type,x-gus-key")
        self.send_header("access-control-allow-methods", "GET,PUT,POST,DELETE")

    def run(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/blob/"):
            key = path[len("/blob/"):]
            if self.command == "PUT":
                OBJECTS[key] = self.rfile.read(int(self.headers.get("content-length", 0)))
                self.send_response(200); self.cors(); self.end_headers(); return
            data = OBJECTS.get(key)
            self.send_response(200 if data else 404); self.cors(); self.end_headers()
            if data:
                self.wfile.write(data)
            return
        length = int(self.headers.get("content-length", 0))
        event = {
            "requestContext": {"http": {"method": self.command}},
            "rawPath": path,
            "headers": dict(self.headers),
            "body": self.rfile.read(length).decode() if length else None,
        }
        out = handler.handler(event, None)
        self.send_response(out["statusCode"])
        self.cors()
        for k, v in out["headers"].items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(out["body"].encode())

    do_GET = do_PUT = do_POST = do_DELETE = run

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8714), Relay).serve_forever()
