"""GUS relay: keeps Gus's documents and passes only revealed ones to the player page.

Storage is one private S3 bucket:
  vault.json   every document, with game master notes (game master key only)
  public.json  revealed copies and the last push (player key or game master key)
  assets/<id>  attachments, served through short-lived signed links

Access keys are never stored here. SSM Parameter Store holds only their SHA-256 hashes.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid

import boto3
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "ca-central-1")
BUCKET = os.environ["BUCKET"]
S3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)
SSM = boto3.client("ssm", region_name=REGION)

VAULT, PUBLIC = "vault.json", "public.json"
DOC_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
ASSET_ID = re.compile(r"^[a-f0-9]{32}$")
TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}
KINDS = {"protocol", "letter", "annex", "log", "report", "image", "other"}
TEXT_LIMITS = {
    "title": 200, "ref": 120, "classification": 120, "from": 200, "to": 200,
    "date": 120, "body": 60000, "note": 20000,
}
PUBLIC_FIELDS = ("title", "ref", "kind", "classification", "from", "to", "date", "body", "asset", "order")

_hashes = None


def now():
    return int(time.time() * 1000)


def hashes():
    global _hashes
    if _hashes is None:
        names = ["/osse/gus/gm-key-sha256", "/osse/gus/player-key-sha256"]
        found = SSM.get_parameters(Names=names, WithDecryption=True)["Parameters"]
        by_name = {p["Name"]: p["Value"] for p in found}
        _hashes = (by_name[names[0]], by_name[names[1]])
    return _hashes


def role(headers):
    key = headers.get("x-gus-key", "")
    if not key or len(key) > 200:
        return None
    digest = hashlib.sha256(key.encode()).hexdigest()
    gm, player = hashes()
    if hmac.compare_digest(digest, gm):
        return "gm"
    if hmac.compare_digest(digest, player):
        return "player"
    return None


def load(key, empty):
    try:
        return json.loads(S3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except S3.exceptions.NoSuchKey:
        return empty


def save(key, obj):
    S3.put_object(
        Bucket=BUCKET, Key=key, Body=json.dumps(obj, ensure_ascii=False).encode(),
        ContentType="application/json",
    )


def reply(code, body=None):
    return {
        "statusCode": code,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(body if body is not None else {}, ensure_ascii=False),
    }


def clean(body):
    doc = {}
    for field, limit in TEXT_LIMITS.items():
        value = body.get(field, "")
        doc[field] = value[:limit] if isinstance(value, str) else ""
    kind = body.get("kind")
    doc["kind"] = kind if kind in KINDS else "other"
    order = body.get("order")
    doc["order"] = order if isinstance(order, (int, float)) and not isinstance(order, bool) else 99
    asset = body.get("asset")
    if isinstance(asset, dict) and ASSET_ID.match(str(asset.get("id", ""))) and asset.get("type") in TYPES:
        name = asset.get("name", "")
        doc["asset"] = {"id": asset["id"], "type": asset["type"], "name": name[:200] if isinstance(name, str) else ""}
    else:
        doc["asset"] = None
    doc["updatedAt"] = now()
    return doc


def black_out(text):
    """||secret|| becomes a bar of the same length, so the player copy never holds the words."""
    return re.sub(r"\|\|(.+?)\|\|", lambda m: "||" + "█" * min(40, max(3, len(m.group(1)))) + "||", text or "")


def public_copy(doc, revealed_at):
    copy = {field: doc.get(field) for field in PUBLIC_FIELDS}
    copy["body"] = black_out(copy.get("body"))
    copy["revealedAt"] = revealed_at or now()
    return copy


def links(docs):
    out = {}
    for doc in docs:
        asset = (doc or {}).get("asset")
        if asset and ASSET_ID.match(asset.get("id", "")):
            out[asset["id"]] = S3.generate_presigned_url(
                "get_object", Params={"Bucket": BUCKET, "Key": "assets/" + asset["id"]}, ExpiresIn=3600,
            )
    return out


def drop_asset(asset):
    if asset and ASSET_ID.match(asset.get("id", "")):
        S3.delete_object(Bucket=BUCKET, Key="assets/" + asset["id"])


def handler(event, _context):
    method = event["requestContext"]["http"]["method"]
    if method == "OPTIONS":
        return reply(204)
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    who = role(headers)
    if who is None:
        return reply(401, {"error": "locked"})

    parts = (event.get("rawPath") or "/").strip("/").split("/")
    pub = load(PUBLIC, {"rev": 0, "shelf": {}, "signal": None})

    if method == "GET" and parts == ["files"]:
        return reply(200, {**pub, "links": links(pub["shelf"].values())})
    if who != "gm":
        return reply(403, {"error": "game master only"})

    vault = load(VAULT, {"docs": {}})
    docs = vault["docs"]

    def full():
        return reply(200, {"vault": vault, **pub, "links": links(docs.values())})

    if method == "GET" and parts == ["gm"]:
        return full()

    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        body = json.loads(raw)
    except ValueError:
        return reply(400, {"error": "bad json"})
    if not isinstance(body, dict):
        return reply(400, {"error": "bad json"})

    if method == "POST" and parts == ["gm", "upload"]:
        kind = body.get("type")
        if kind not in TYPES:
            return reply(400, {"error": "Use a PNG, JPEG, GIF, WebP or PDF file."})
        asset_id = uuid.uuid4().hex
        put = S3.generate_presigned_url(
            "put_object", Params={"Bucket": BUCKET, "Key": "assets/" + asset_id, "ContentType": kind}, ExpiresIn=600,
        )
        return reply(200, {"id": asset_id, "put": put})

    if len(parts) != 3 or parts[0] != "gm" or not DOC_ID.match(parts[2]):
        return reply(404, {"error": "not found"})
    op, doc_id = parts[1], parts[2]
    signal = pub.get("signal") or {}

    if op == "doc" and method == "PUT":
        old = docs.get(doc_id, {}).get("asset")
        doc = clean(body)
        docs[doc_id] = doc
        save(VAULT, vault)
        if doc_id in pub["shelf"]:
            pub["shelf"][doc_id] = public_copy(doc, pub["shelf"][doc_id].get("revealedAt"))
            pub["rev"] += 1
            save(PUBLIC, pub)
        if old and (not doc["asset"] or doc["asset"]["id"] != old.get("id")):
            drop_asset(old)
        return full()

    if op == "doc" and method == "DELETE":
        doc = docs.pop(doc_id, None)
        save(VAULT, vault)
        pub["shelf"].pop(doc_id, None)
        if signal.get("id") == doc_id:
            pub["signal"] = None
        pub["rev"] += 1
        save(PUBLIC, pub)
        drop_asset((doc or {}).get("asset"))
        return full()

    if method != "POST" or op not in ("reveal", "push", "hide"):
        return reply(404, {"error": "not found"})
    if op in ("reveal", "push"):
        if doc_id not in docs:
            return reply(404, {"error": "not found"})
        if doc_id not in pub["shelf"]:
            pub["shelf"][doc_id] = public_copy(docs[doc_id], now())
        if op == "push":
            pub["signal"] = {"id": doc_id, "at": now()}
    else:
        pub["shelf"].pop(doc_id, None)
        if signal.get("id") == doc_id:
            pub["signal"] = None
    pub["rev"] += 1
    save(PUBLIC, pub)
    return full()
