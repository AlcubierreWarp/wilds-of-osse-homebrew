"""Adds or revises one document in Gus's archive. New documents stay sealed: only the game master sees them.

Usage:
  /usr/bin/python3 -I relay/gus/add_doc.py <document.md> [--pdf file.pdf] [--mock] [--update-revealed]

The document file starts with a header block, then the body in the page markup the archive lays out:

  ---
  id: mi-fm-01-anx-b
  kind: annex            (manual, annex, protocol, letter, log, report, image or other)
  title: Social camouflage
  ref: MI/FM-01/ANX-B · Annex B to Chapter One
  classification: Decrypted
  from: Steven (Construct). Reviewed by Steven (a different one)
  to: General Service Unit Seven
  date:
  order: 5               (optional; defaults to the end of the list)
  note: Why it exists and when to hand it over. Never shown to Gus.
  ---
  Annex B to Chapter One · Subtitle
  *Italic intro.*
  ...

Nothing is ever revealed or pushed from here. Tom does that from the archive page at the table.
A document Gus can already see is only changed with --update-revealed, because the change reaches Gus at once.
The game master key is read from the macOS Keychain inside this process and never printed.
Sealed documents are game secrets: only the game master view shows them until Tom reveals them at the table.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

RELAY = "https://2srnsytz3rqi3jke23bz643jhq0irvei.lambda-url.ca-central-1.on.aws"
FIELDS = ("title", "ref", "kind", "classification", "from", "to", "date", "note")
KINDS = {"manual", "protocol", "letter", "annex", "log", "report", "image", "other"}


def fail(msg):
    sys.exit("add_doc: " + msg)


def parse(text):
    lines = text.replace("\r", "").split("\n")
    if not lines or lines[0].strip() != "---":
        fail("the file must start with a --- header block")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        fail("the header block has no closing ---")
    head = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            fail(f"header line without a colon: {line!r}")
        head[key.strip().lower()] = value.strip()
    head["body"] = "\n".join(lines[end + 1:]).strip("\n")
    return head


def main():
    args = sys.argv[1:]
    flags = {a for a in args if a.startswith("--") and a != "--pdf"}
    pdf = None
    if "--pdf" in args:
        i = args.index("--pdf")
        if i + 1 >= len(args):
            fail("--pdf needs a file")
        pdf = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    files = [a for a in args if not a.startswith("--")]
    if len(files) != 1:
        fail("give exactly one document file")
    doc = parse(Path(files[0]).read_text(encoding="utf-8"))

    doc_id = doc.pop("id", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,59}", doc_id):
        fail("id must be lowercase letters, digits and hyphens, for example mi-fm-03")
    if doc.get("kind") not in KINDS:
        fail("kind must be one of " + ", ".join(sorted(KINDS)))
    if not doc.get("title"):
        fail("title is required")

    if "--mock" in flags:
        relay, key = "http://localhost:8714", "test-gm"
    else:
        relay = RELAY
        key = subprocess.check_output(
            ["security", "find-generic-password", "-a", "osse", "-s", "osse-gus-gm", "-w"]).decode().strip()

    def call(method, path, body=None, url=None):
        req = urllib.request.Request(
            url or relay + path, method=method,
            headers={"x-gus-key": key, "content-type": "application/json"} if not url else {"content-type": "application/pdf"},
            data=body if url else (json.dumps(body).encode() if body is not None else None))
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw and not url else None

    state = call("GET", "/gm")
    old = state["vault"]["docs"].get(doc_id)
    revealed = doc_id in state["shelf"]
    if revealed and "--update-revealed" not in flags:
        fail(f"{doc_id} is already revealed to Gus. Add --update-revealed to change his copy too.")

    out = {f: doc.get(f, "") for f in FIELDS}
    if old and "note" not in doc:
        out["note"] = old.get("note", "")
    if doc.get("order", "").strip():
        out["order"] = float(doc["order"]) if "." in doc["order"] else int(doc["order"])
    elif old:
        out["order"] = old.get("order", 99)
    else:
        orders = [d.get("order", 0) for d in state["vault"]["docs"].values() if isinstance(d.get("order"), (int, float))]
        out["order"] = int(max(orders, default=0)) + 1
    out["body"] = doc["body"]

    if pdf:
        up = call("POST", "/gm/upload", {"type": "application/pdf"})
        call("PUT", None, pdf.read_bytes(), url=up["put"])
        out["asset"] = {"id": up["id"], "type": "application/pdf", "name": pdf.name}
    else:
        out["asset"] = (old or {}).get("asset")

    call("PUT", "/gm/doc/" + doc_id, out)
    status = "revealed, Gus's copy updated" if revealed else "sealed, only the game master sees it"
    print(f"{'Revised' if old else 'Added'} {doc_id}: {out['title']} ({status}).")


if __name__ == "__main__":
    main()
