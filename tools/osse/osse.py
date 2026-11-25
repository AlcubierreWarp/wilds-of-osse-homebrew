#!/usr/bin/env python3
"""Compact answers about the Ossë vault, sized for Claude to read. Start every campaign question here.
  python3 tools/osse/osse.py brief                 where the campaign stands: last session, open questions, plans for next
  python3 tools/osse/osse.py card "Mira Holt"      one entry: facts, now, DM notes, strongest current links, recent log
  python3 tools/osse/osse.py card "Mira Holt" --full   the whole note as written
  python3 tools/osse/osse.py find bell             names, aliases and summaries; --body also searches note text
  python3 tools/osse/osse.py plans                 live plans by target; --checks for the judgment calls only
  python3 tools/osse/osse.py scene "The gala"      a scene plan as a run sheet: situation, purpose, beats with their cues, exits; no name lists them
  python3 tools/osse/osse.py walk "Mira Holt" ...  the full graph walk (tools/osse/graph.py and its options)
  python3 tools/osse/osse.py build [--dry]         rebuild the generated files and the vault/ DM pages (tools/osse/build.py)
  python3 tools/osse/osse.py page "Mira Holt"      where that entry's DM page is (vault/, rebuilt by every build)
Reads the vault's .osse/graph.json (rebuilt by build.py) and the notes themselves. Never writes."""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.environ.get("OSSE_VAULT") or os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ossë")
LINK = re.compile(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]")
LIVE = {"draft", "ready"}


def load():
    g = json.load(open(os.path.join(VAULT, ".osse", "graph.json"), encoding="utf-8"))
    return g, {n["id"]: n for n in g["nodes"]}


def text(node):
    return open(os.path.join(VAULT, node["path"]), encoding="utf-8").read()


def body(t):
    return t.split("\n---", 1)[1].split("\n", 1)[1] if t.startswith("---") and "\n---" in t[3:] else t


def sections(t):
    out, cur = {}, None
    for line in body(t).splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: [x for x in v if x.strip()] for k, v in out.items()}


def plain(s):
    return LINK.sub(r"\1", s)


def resolve(nodes, q):
    ql = q.lower().strip()
    for n in nodes.values():
        if n["id"].lower() == ql or ql in [str(a).lower() for a in n.get("aliases", [])]:
            return n["id"]
    hits = [i for i in nodes if ql in i.lower()] or \
           [n["id"] for n in nodes.values() if any(ql in str(a).lower() for a in n.get("aliases", []))]
    if len(hits) == 1:
        return hits[0]
    sys.exit(f"No single match for {q!r}" + (f"; did you mean: {', '.join(hits[:12])}" if hits else ""))


def head(n):
    bits = [n.get("term") or n["type"]]
    for k in ("kind", "state", "location", "in", "holder", "role", "status", "target", "revealed", "importance"):
        if n.get(k) not in (None, "", []):
            bits.append(f"{k} {n[k]}")
    if n.get("stage") not in (None, "canon"):
        bits.append(n["stage"])
    if n.get("first_seen"):
        bits.append(f"since {n['first_seen']}")
    return f"{n['id']} ({'; '.join(map(str, bits))})"


def current(e, cur):
    if e.get("layer") == "draft":
        return False
    if e.get("start") is not None and e["start"] > cur:
        return False
    return e.get("end") is None or e["end"] > cur


# ---------- commands ----------
def brief(g, nodes):
    cur = g.get("current_session", 0)
    sess = sorted((n for n in nodes.values() if n["type"] == "session" and str(n.get("number", "")).isdigit()),
                  key=lambda n: int(n["number"]))
    last = next((n for n in reversed(sess) if int(n["number"]) == cur), sess[-1] if sess else None)
    print(f"Ossë after S{cur}" + (f": {last['id']}" if last else ""))
    if last:
        if last.get("summary"):
            print(plain(last["summary"]))
        sec = sections(text(last))
        for k, v in sec.items():
            if k.startswith("Open going into"):
                print(f"\n{k}:"); print("\n".join(plain(x) for x in v))
    nxt = cur + 1
    plans = [n for n in nodes.values() if n["type"] == "plan" and n.get("status") in LIVE]
    aimed = [n for n in plans if str(n.get("target", "")).upper() in (f"S{nxt}", f"S{cur}")]
    if aimed:
        print(f"\nPlans aimed at S{nxt} ({len(aimed)} of {len(plans)} live; `plans` for all):")
        for n in sorted(aimed, key=lambda n: (n.get("status") != "ready", n["id"])):
            print(f"- [{n['status']}] {n['id']}: {plain(n.get('summary', ''))}")
    th = [n for n in nodes.values() if n["type"] == "thread" and n.get("status", "open") == "open"]
    print(f"\nOpen threads ({len(th)}):")
    for n in sorted(th, key=lambda n: (-int(n.get("importance") or 0), n["id"])):
        print(f"- {n['id']}: {plain(n.get('summary', ''))}")
    if g.get("problems"):
        print(f"\nBuild problems: {len(g['problems'])} (run `build --dry`)")


def card(g, nodes, q, full=False, nlinks=12):
    nid = resolve(nodes, q); n = nodes[nid]; t = text(n)
    if full:
        print(t); return
    print(head(n))
    if n.get("aliases"):
        print("aka " + ", ".join(map(str, n["aliases"])))
    if n.get("summary"):
        print(plain(n["summary"]))
    sec = sections(t)
    lead = {"session": ["What happened", "What changed"], "secret": ["The truth", "Who knows", "How it could come out"],
            "thread": ["The question", "What the party knows"], "plan": ["Idea", "Requires", "Links"]}.get(n["type"], ["Now"])
    for k in lead:
        if sec.get(k):
            print(f"\n{k}:"); print("\n".join(plain(x) for x in sec[k][:12]))
    if n["type"] not in ("secret", "session", "plan"):
        first = [x for x in sec.get("Who they are", sec.get("What it is", [])) if not x.startswith(">")][:3]
        if first:
            print("\nAbout:"); print("\n".join(plain(x) for x in first))
    dm = [ln[1:].strip() for ln in body(t).splitlines() if ln.startswith(">") and "[!" not in ln]
    if dm:
        print("\nDM only:"); print("\n".join(plain(x) for x in dm))
    if n["type"] not in ("session", "plan"):
        cur, seen, rows = g.get("current_session", 0), set(), []
        for e in g["edges"]:
            if e.get("origin") not in ("written", "property") or not current(e, cur) or nid not in (e["from"], e["to"]):
                continue
            fwd = e["from"] == nid
            other, typ = (e["to"], e["type"]) if fwd else (e["from"], e["inverse"])
            key = (other, typ)
            if key in seen:
                continue
            seen.add(key)
            rows.append((-int(e.get("weight") or 0), other, typ, e))
        rows.sort()
        if rows:
            print(f"\nLinks now ({len(rows)}{f', top {nlinks}' if len(rows) > nlinks else ''}):")
            for w, other, typ, e in rows[:nlinks]:
                extra = " · ".join(x for x in (e.get("layer") if e.get("layer") == "prep" else "", e.get("note") or "") if x)
                print(f"- {'●' * -w} {typ}: {other}" + (f" ({extra})" if extra else ""))
    log = [x for x in sec.get("Session Log", sec.get("Log", [])) if x.startswith("| S") or x.startswith("- S")]
    if log:
        print("\nLast log:"); print("\n".join(plain(x) for x in log[-3:]))
    print(f"\n{n['path']}")


def find(g, nodes, q, in_body=False):
    ql = q.lower(); found = 0
    for n in sorted(nodes.values(), key=lambda n: n["id"]):
        hay = " ".join([n["id"]] + [str(a) for a in n.get("aliases", [])] + [str(n.get("summary", ""))]).lower()
        if ql in hay:
            print(f"- {head(n)}: {plain(n.get('summary', ''))}"); found += 1
        elif in_body:
            hits = [ln.strip() for ln in body(text(n)).splitlines() if ql in ln.lower()]
            if hits:
                print(f"- {n['id']}: {plain(hits[0])[:200]}" + (f" (+{len(hits) - 1} more)" if len(hits) > 1 else "")); found += 1
    if not found:
        print("nothing found" + ("" if in_body else "; try --body"))


def plans(g, nodes, checks=False):
    live = [n for n in nodes.values() if n["type"] == "plan" and n.get("status") in LIVE]
    for n in sorted(live, key=lambda n: (str(n.get("target") or "S999"), n["status"] != "ready", n["id"])):
        req = sections(text(n)).get("Requires", [])
        calls = [plain(x)[2:].split(":", 1)[1].strip() for x in req if x.startswith("- check:")]
        if checks and not calls:
            continue
        print(f"- {n.get('target') or 'no target'} [{n['status']}] {n['id']}: {plain(n.get('summary', ''))}")
        for c in calls:
            print(f"    check: {c}")


def scene(g, nodes, q=None):
    """A scene put back together from the plan notes that name it."""
    live = [n for n in nodes.values() if n["type"] == "plan" and n.get("status") in LIVE]
    if not q:
        for n in sorted((n for n in live if n.get("kind") == "scene"), key=lambda n: (str(n.get("target") or "S999"), n["id"])):
            print(f"- {n.get('target') or 'no target'} {n['id']}: {plain(n.get('purpose') or n.get('summary', ''))} ({sum(m.get('scene') == n['id'] for m in live)} cards)")
        return
    nid = resolve(nodes, q); n = nodes[nid]
    many = lambda v: ", ".join(map(str, v)) if isinstance(v, list) else str(v)
    print(f"SCENE {nid} [{n.get('status')}{', ' + n['target'] if n.get('target') else ''}]")
    print("Situation: " + " · ".join(many(n[k]) for k in ("where", "when", "present") if n.get(k)))
    for ln in sections(text(n)).get("Idea", []):
        print("  " + plain(ln).lstrip("- "))
    print(f"Purpose: {n.get('purpose') or '(not set)'}")
    inn = {m["id"]: m for m in live if m.get("scene") == nid}
    needs, opts = {}, {}
    for m in inn.values():
        s = sections(text(m))
        needs[m["id"]] = [x for ln in s.get("Requires", []) if ln.startswith(("- plan:", "- played:")) for x in LINK.findall(ln) if x in inn]
        opts[m["id"]] = [(x.group(1), b.strip()) if x else (plain(b.strip()), plain(a.strip())) for a, _, b in (ln[2:].partition("·") for ln in s.get("Options", []) if ln.startswith("- ")) for x in [LINK.match(a.strip())]]
        opts[m["id"]] += [(x, "") for x in (m.get("leads_to") if isinstance(m.get("leads_to"), list) else [m["leads_to"]] if m.get("leads_to") else [])]
    under = {}
    for m, ps in needs.items():
        if ps: under[m] = ps[0]
    for m, os_ in opts.items():
        for t, _ in os_:
            if t in inn and inn[m].get("kind") == "decision": under.setdefault(t, m)
    seen = set()

    def show(mid, d):
        if mid in seen: return
        seen.add(mid); m = inn[mid]; pad = "  " * d; k = m.get("kind") or "beat"
        print(f"{pad}- {'CRITICAL ' if str(m.get('critical', '')).lower() == 'true' else ''}{k.upper()} {mid}" + (f" ({m['clock']})" if m.get("clock") else ""))
        if m.get("cue"): print(f"{pad}    cue: {m['cue']}")
        if m.get("who"): print(f"{pad}    who: {many(m['who'])}")
        if m.get("reveals"): print(f"{pad}    reveals: {many(m['reveals'])}")
        for ln in sections(text(m)).get("Idea", []): print(f"{pad}    {plain(ln).lstrip('- ')}")
        for t, lab in opts[mid]: print(f"{pad}    {'option: ' + lab + ' → ' if k == 'decision' else 'leads to '}{t}")
        for c in inn:
            if under.get(c) == mid: show(c, d + 1)

    yes = lambda m: str(m.get("anytime") or "").lower() in ("true", "yes", "1")
    for head_, ok in (("Any time:", yes), ("Beats:", lambda m: m.get("kind") != "exit" and not yes(m)), ("Exits:", lambda m: m.get("kind") == "exit" and not yes(m))):
        tops = [m for m in inn if m not in under and ok(inn[m]) and m not in seen]
        if tops: print(head_)
        for m in tops: show(m, 1)
    for m in list(inn):
        show(m, 1)   # anything caught in a loop


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__); sys.exit()
    cmd, rest = a[0], a[1:]
    if cmd == "build":
        sys.exit(subprocess.call([sys.executable, os.path.join(HERE, "build.py")] + rest))
    if cmd == "walk":
        sys.exit(subprocess.call([sys.executable, os.path.join(HERE, "graph.py")] + rest))
    g, nodes = load()
    if cmd == "page" and rest:
        import pages
        site = pages.Site(g); nid = resolve(nodes, " ".join(w for w in rest if not w.startswith("--")))
        f = site.slugs[nid] + ".html"
        print(f"{nid}\n  local: {os.path.join(pages.OUT, f)}\n  site:  {pages.SITE}{f}")
        sys.exit()
    words = [x for x in rest if not x.startswith("--")]
    if cmd == "brief":
        brief(g, nodes)
    elif cmd == "card" and words:
        for w in words:
            card(g, nodes, w, full="--full" in rest)
            if len(words) > 1:
                print()
    elif cmd == "find" and words:
        find(g, nodes, " ".join(words), "--body" in rest)
    elif cmd == "scene":
        scene(g, nodes, " ".join(words) or None)
    elif cmd == "plans":
        plans(g, nodes, "--checks" in rest)
    else:
        print(__doc__); sys.exit(1)
