#!/usr/bin/env python3
"""The players' chronicle: session recaps that live in the Ossë vault and are published on the site.

The vault (iCloud, game master only) is the source of truth. Its `Chronicle/` folder is the one part of it
written for the players: one note per played session, plus `Chronicle/Quest lines.md`. Nothing else in the
vault is ever read for publishing, so secrets and plans cannot leak.

  python3 tools/chronicle.py note <session.json> [--force]
      Writes (or replaces) the vault note Chronicle/S<n> - <title>.md from an extracted recap,
      linking the first mention of every name that has a vault entry. A link shows as bold on the site.
  python3 tools/chronicle.py export
      Reads Chronicle/ and writes chronicle/chronicle.json in this repository.

Session JSON (from the Notion player summary, for now):
  {"n": 12, "title": "...", "notion": "https://...", "summary": ["para", ...],
   "quests": [{"name", "status": "new|changed|none|resolved", "text", "clues": []}],
   "npcs": [{"name", "title", "faction", "role", "state", "new", "text"}],
   "items": [{"name", "homebrew", "new", "text"}]}
"""
import json, os, re, sys

VAULT = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ossë")
CHRON = os.path.join(VAULT, "Chronicle")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "chronicle", "chronicle.json")
# Entries that may be linked (and so bolded) in player text. Secrets, threads, plans and sessions never are.
LINKABLE = ["Characters", "People", "Factions", "Places", "Things", "Lore"]
PROPS = {"status", "title", "faction", "role", "state", "new", "homebrew", "aim", "also called", "thread", "opened"}


def fail(msg):
    sys.exit("chronicle: " + msg)


def frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    fm = {}
    for line in text[3:end].splitlines():
        k, sep, v = line.partition(":")
        if sep and not line.startswith(" "):
            fm[k.strip()] = v.strip().strip('"')
    return fm, text[end + 4:]


# ---------- linking names ----------
def names():
    """Every linkable note name and alias -> note name."""
    out = {}
    for folder in LINKABLE:
        for root, _, files in os.walk(os.path.join(VAULT, folder)):
            for f in files:
                if not f.endswith(".md"):
                    continue
                note = f[:-3]
                text = open(os.path.join(root, f), encoding="utf-8").read()
                out.setdefault(note, note)
                m = re.search(r"^aliases:\s*\[(.*?)\]\s*$", text, re.M)
                al = [a.strip().strip('"\'') for a in m.group(1).split(",")] if m else []
                if not m:
                    block = re.search(r"^aliases:\s*\n((?:\s+- .*\n)+)", text, re.M)
                    if block:
                        al = [x.strip()[2:].strip().strip('"\'') for x in block.group(1).splitlines()]
                for a in al:
                    if len(a) >= 3 and a[:1].isupper() and a not in out:
                        out[a] = note
    return out


def linker():
    table = names()
    keys = sorted(table, key=len, reverse=True)
    pat = re.compile(r"(?<![\w'])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w])")

    def link(text, seen=None):
        """Link the first mention of each entry in this paragraph."""
        seen = set() if seen is None else seen
        parts = re.split(r"(\[\[.*?\]\])", text)
        for i, part in enumerate(parts):
            if part.startswith("[["):
                continue
            def sub(m):
                note = table[m.group(1)]
                if note in seen:
                    return m.group(1)
                seen.add(note)
                return f"[[{note}]]" if note == m.group(1) else f"[[{note}|{m.group(1)}]]"
            parts[i] = pat.sub(sub, part)
        return "".join(parts)
    return link, table


# ---------- vault note ----------
def note(path, force):
    s = json.load(open(path, encoding="utf-8"))
    n, title = int(s["n"]), s["title"].strip()
    link, table = linker()
    safe = re.sub(r'[*"\\/<>|?#^\[\]]', "", title).replace(":", " -")
    fname = f"S{n} - {safe}.md"
    os.makedirs(CHRON, exist_ok=True)
    for f in os.listdir(CHRON):
        if f.startswith(f"S{n} - ") and f != fname:
            fail(f"a chronicle note for S{n} already exists as {f}")
    dest = os.path.join(CHRON, fname)
    if os.path.exists(dest) and not force:
        fail(f"{fname} exists; add --force to replace it (Tom may have edited it)")
    sess = [f[:-3] for f in os.listdir(os.path.join(VAULT, "Sessions")) if f.startswith(f"S{n} - ")]
    L = ["---", "type: chronicle", f"number: {n}", f"title: {title}"]
    if sess:
        L.append(f'session: "[[{sess[0]}]]"')
    if s.get("notion"):
        L.append(f"notion: {s['notion']}")
    L += ["---", "", "> [!info] Players' chronicle",
          "> Everything in this note is published on the players' chronicle page. Write only what the table saw. A link to a vault note shows in bold.",
          "", "## Summary", ""]
    for p in s.get("summary", []):
        L += [link(p.strip()), ""]
    L += ["## Quest lines", ""]
    for q in s.get("quests", []):
        L += [f"### {q['name'].strip()}", f"- status: {q.get('status') or 'changed'}"]
        if q.get("text"):
            L += [link(q["text"].strip())]
        L += [f"- Clue: {link(c.strip())}" for c in q.get("clues") or []]
        L.append("")
    L += ["## NPCs", ""]
    for p in s.get("npcs", []):
        nm = p["name"].strip()
        L.append(f"### {link(nm)}")
        for k in ("title", "faction", "role", "state"):
            if (p.get(k) or "").strip():
                L.append(f"- {k}: {p[k].strip()}")
        if p.get("new"):
            L.append("- new: yes")
        if p.get("text"):
            L.append(link(p["text"].strip()))
        L.append("")
    L += ["## Items", ""]
    for it in s.get("items", []):
        L.append(f"### {it['name'].strip()}")
        if it.get("homebrew"):
            L.append(f"- homebrew: {it['homebrew']}")
        if it.get("new"):
            L.append("- new: yes")
        if it.get("text"):
            L.append(link(it["text"].strip()))
        L.append("")
    open(dest, "w", encoding="utf-8").write("\n".join(L).rstrip() + "\n")
    print(f"Wrote Chronicle/{fname}")


# ---------- export ----------
def plain(text):
    """Vault markup -> site markup: [[Note|shown]] and [[Note]] become **bold**; only the shown text is kept."""
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"**\2**", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"**\1**", text)
    return text.replace("****", "")


def blocks(body):
    """## Section -> ### Heading -> {props, text: [para], clues: []}"""
    out, sec, cur = {}, None, None
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            sec = line[3:].strip(); out[sec] = {"paras": [], "items": []}; cur = None; continue
        if sec is None or line.startswith(">"):
            continue
        if line.startswith("### "):
            cur = {"head": line[4:].strip(), "props": {}, "text": [], "clues": []}
            out[sec]["items"].append(cur); continue
        m = re.match(r"^- ([A-Za-z ]+):\s*(.*)$", line)
        if cur is not None and m and m.group(1).lower() in PROPS:
            cur["props"][m.group(1).lower()] = m.group(2).strip(); continue
        if cur is not None and m and m.group(1).lower() == "clue":
            cur["clues"].append(plain(m.group(2).strip())); continue
        if not line.strip():
            continue
        (cur["text"] if cur is not None else out[sec]["paras"]).append(plain(line.strip()))
    return out


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def export():
    if not os.path.isdir(CHRON):
        fail("no Chronicle folder in the vault yet")
    qpath = os.path.join(CHRON, "Quest lines.md")
    quests, alias = [], {}
    if os.path.exists(qpath):
        _, body = frontmatter(open(qpath, encoding="utf-8").read())
        for q in blocks(body).get("Quest lines", {}).get("items", []):
            name = plain(q["head"]).replace("**", "")
            qid = slug(name)
            quests.append({"id": qid, "name": name, "aim": " ".join(q["text"]) or q["props"].get("aim", "")})
            alias[name.lower()] = qid
            for a in q["props"].get("also called", "").split(";"):
                if a.strip():
                    alias[a.strip().lower()] = qid
    sessions, problems = [], []
    for f in sorted(os.listdir(CHRON)):
        if not re.match(r"S\d+ - .*\.md$", f):
            continue
        fm, body = frontmatter(open(os.path.join(CHRON, f), encoding="utf-8").read())
        if fm.get("publish", "yes").lower() in ("no", "false"):
            continue
        b = blocks(body)
        s = {"n": int(fm.get("number") or re.match(r"S(\d+)", f).group(1)), "title": fm.get("title") or f[:-3].split(" - ", 1)[1],
             "summary": b.get("Summary", {}).get("paras", []), "quests": [], "npcs": [], "items": []}
        for q in b.get("Quest lines", {}).get("items", []):
            name = plain(q["head"]).replace("**", "")
            qid = alias.get(name.lower())
            if not qid:
                problems.append(f"{f}: quest '{name}' is not in Quest lines.md (add it, or add the name under 'also called')")
                qid = slug(name); alias[name.lower()] = qid
                quests.append({"id": qid, "name": name, "aim": ""})
            s["quests"].append({"id": qid, "status": q["props"].get("status", "changed"), "text": " ".join(q["text"]), "clues": q["clues"]})
        for p in b.get("NPCs", {}).get("items", []):
            s["npcs"].append({"name": plain(p["head"]).replace("**", ""), **{k: p["props"].get(k, "") for k in ("title", "faction", "role", "state")},
                              "new": p["props"].get("new", "").lower() in ("yes", "true"), "text": " ".join(p["text"])})
        for it in b.get("Items", {}).get("items", []):
            s["items"].append({"name": plain(it["head"]).replace("**", ""), "homebrew": it["props"].get("homebrew", ""),
                               "new": it["props"].get("new", "").lower() in ("yes", "true"), "text": " ".join(it["text"])})
        sessions.append(s)
    sessions.sort(key=lambda s: s["n"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = {"quests": quests, "sessions": sessions}
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if "[[" in text:
        problems.append("a [[link]] survived the export")
    open(OUT, "w", encoding="utf-8").write(text + "\n")
    print(f"Exported {len(sessions)} sessions and {len(quests)} quest lines to chronicle/chronicle.json")
    for p in problems:
        print("  ! " + p)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["note"] and len(a) >= 2:
        note(a[1], "--force" in a)
    elif a[:1] == ["export"]:
        export()
    else:
        fail(__doc__)
