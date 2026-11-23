#!/usr/bin/env python3
"""Stop real-world secrets reaching this public repository. Game secrets are fine; this looks only for real ones.
  python3 tools/check_secrets.py            check every file git tracks or is about to track
  python3 tools/check_secrets.py --staged   check only what is staged (the pre-commit hook runs this)
Finds: cloud and service keys and tokens, private keys, signed URLs (AWS and Notion file links expire but carry
live credentials), passwords in config lines, and email addresses or phone numbers. Exits 1 and names each hit.
A line that must stay can end with the marker  check-secrets: allow  and a reason."""
import os, re, subprocess, sys

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
PATTERNS = [
    ("AWS access key", r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
    ("AWS secret key", r"(?i)aws.{0,20}secret.{0,20}['\"=: ]+[A-Za-z0-9/+=]{40}\b"),
    ("signed URL (temporary credentials)", r"X-Amz-(?:Signature|Security-Token|Credential)=|[?&]Signature=[A-Za-z0-9%]{20,}"),
    ("private key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY"),
    ("GitHub token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("Anthropic or OpenAI key", r"\bsk-(?:ant-)?[A-Za-z0-9_-]{24,}"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("Stripe key", r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}"),
    ("Notion token", r"\b(?:secret_[A-Za-z0-9]{40,}|ntn_[A-Za-z0-9]{40,})"),
    ("JSON web token", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("password in config", r"(?i)\b(?:password|passwd|api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|x-gus-key)\b\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"),
    ("email address", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("phone number", r"(?<![\w.#-])(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\w.-])"),
]
EMAIL_OK = re.compile(r"@(?:example\.(?:com|org)|anthropic\.com|users\.noreply\.github\.com)$|^git@github\.com$", re.I)
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ttf", ".otf", ".woff", ".woff2", ".ico", ".zip", ".gz"}
ALLOW = "check-secrets: allow"


def files(staged):
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged else ["git", "ls-files", "-co", "--exclude-standard"]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout.split("\n")
    return [f for f in out if f and os.path.splitext(f)[1].lower() not in SKIP_EXT and os.path.isfile(os.path.join(ROOT, f))]


def scan(path):
    hits = []
    try:
        text = open(os.path.join(ROOT, path), encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return hits
    for n, line in enumerate(text.split("\n"), 1):
        if ALLOW in line:
            continue
        for label, pat in PATTERNS:
            for m in re.finditer(pat, line):
                if label == "email address" and EMAIL_OK.search(m.group(0)):
                    continue
                hits.append((path, n, label, m.group(0)))
    return hits


if __name__ == "__main__":
    staged = "--staged" in sys.argv
    hits = [h for f in files(staged) if f != "tools/check_secrets.py" for h in scan(f)]
    for path, n, label, s in hits:
        shown = s if label in ("email address", "phone number") else s[:6] + "…"
        print(f"SECRET? {path}:{n}: {label}: {shown}")
    if hits:
        print(f"{len(hits)} possible real-world secret(s). Remove them, or end the line with '{ALLOW}: <why>' if it is safe.")
        sys.exit(1)
    print("no real-world secrets found")
