#!/usr/bin/env python3
"""Walk the Ossë vault as a typed graph with session time, from the vault's .osse/graph.json (rebuilt by build.py).
  python3 tools/osse/graph.py "Mira Holt"                 the entry and what is true now: links strongest first, then a second hop
  python3 tools/osse/graph.py "Mira Holt" --depth 1       first hop only
  python3 tools/osse/graph.py "Mira Holt" --history       also ended links, with their periods
  python3 tools/osse/graph.py "Mira Holt" --at S7         what was true after session 7
  python3 tools/osse/graph.py "Mira Holt" --plans         also draft links from live plans
  python3 tools/osse/graph.py "Mira Holt" --no-prep       canon only: what the party could know
  python3 tools/osse/graph.py "Mira Holt" --family deed   one family; --type "member of" for one type
  python3 tools/osse/graph.py "Mira Holt" --all           include plain wikilinks and session appearances
  python3 tools/osse/graph.py --path "Mira Holt" "The Lantern Guild"   how two things connect now, as sentences
  python3 tools/osse/graph.py --find "bell"               search names, aliases and summaries
Links are shown from the starting entry's side: a link written the other way appears as its inverse type."""
import json, os, sys, heapq, re
VAULT = os.environ.get("OSSE_VAULT") or os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ossë")
G = json.load(open(os.path.join(VAULT, ".osse", "graph.json"), encoding="utf-8"))
NODES = {n["id"]: n for n in G["nodes"]}
TYPES = G.get("types", {})
CUR = G.get("current_session", 0)
LIVE = {"draft", "ready"}

args = sys.argv[1:]
VALUE = ("--min", "--depth", "--family", "--type", "--at", "--find")
def opt(k, d=None):
    return args[args.index(k) + 1] if k in args else d
MINW = int(opt("--min", 0)); DEPTH = int(opt("--depth", 2)); FAM = opt("--family"); TYP = opt("--type")
ALL = "--all" in args; HIST = "--history" in args; PLANS = "--plans" in args; NOPREP = "--no-prep" in args
AT = opt("--at"); AT_N = int(re.sub(r"\D", "", AT)) if AT else CUR

def state_of(e):
    if e.get("layer") == "draft":
        return "plan"
    if e.get("date") is not None:
        return "later" if e["date"] > AT_N else "event"
    if e.get("start") is not None and e["start"] > AT_N:
        return "later"
    if e.get("end") is not None and e["end"] <= AT_N:
        return "past"
    return "current"

RANK = {"written": 4, "plan": 3, "property": 2, "log": 1, "plain": 0}
ADJ = {}
for e in G["edges"]:
    if e.get("layer") == "draft" and (not PLANS or e.get("status") not in LIVE):
        continue
    if e["from"] not in NODES or e["to"] not in NODES:
        continue
    for a, b, fwd in ((e["from"], e["to"], True), (e["to"], e["from"], False)):
        t = e["type"] if fwd else e["inverse"]
        ADJ.setdefault(a, {}).setdefault(b, []).append({
            "type": t, "family": TYPES.get(t, {}).get("family", e.get("family")), "weight": e["weight"],
            "origin": e["origin"], "edge": e, "forward": fwd})

def when(e):
    if e.get("date") is not None: return f"S{e['date']}"
    if e.get("start") is not None or e.get("end") is not None:
        return f"{'S' + str(e['start']) if e.get('start') is not None else '?'} → {'S' + str(e['end']) if e.get('end') is not None else ''}".strip()
    return ""

def sentence(e, st):
    core = f"{e['to']} is {e['from']}'s {e['type']}" if e["form"] == "noun" else f"{e['from']} {e['type']} {e['to']}"
    tags = [t for t in (e.get("layer") if e.get("layer") in ("prep", "draft") else "", when(e), f"plan {e['plan']}" if e.get("plan") else "") if t]
    return core + (f" [{st}: {', '.join(tags)}]" if st in ("past", "plan") else f" [{', '.join(tags)}]" if tags else "")

def resolve(q):
    ql = q.lower()
    for n in G["nodes"]:
        if n["id"].lower() == ql or ql in [str(a).lower() for a in n.get("aliases", [])]:
            return n["id"]
    hits = [n["id"] for n in G["nodes"] if ql in n["id"].lower()]
    if len(hits) == 1:
        return hits[0]
    sys.exit(f"No single match for {q!r}: {hits[:10]}")

def line(nid):
    n = NODES[nid]
    bits = [n.get("type", "")] + [f"{k}: {n[k]}" for k in ("stage", "state", "location", "status", "target", "importance") if k in n and n[k] not in ("canon",)]
    return f"{nid} ({', '.join(b for b in bits if b)})" + (f" - {n['summary']}" if n.get("summary") else "")

def views(nid, tgt):
    out = []
    for v in ADJ.get(nid, {}).get(tgt, []):
        if not ALL and v["origin"] in ("plain", "log"): continue
        if NOPREP and v["edge"].get("layer") == "prep": continue
        if FAM and v["family"] != FAM: continue
        if TYP and v["type"] != TYP: continue
        if v["weight"] < MINW: continue
        st = state_of(v["edge"])
        if st == "later": continue
        if st == "past" and not HIST: continue
        out.append(dict(v, state=st))
    out.sort(key=lambda v: (-RANK.get(v["origin"], 0), -v["forward"], -v["weight"]))
    seen, keep = set(), []
    for v in out:
        key = (v["type"], when(v["edge"]), v["edge"].get("plan"))
        if key in seen: continue
        seen.add(key); keep.append(v)
    return keep

def links(nid):
    out = [(t, v) for t in ADJ.get(nid, {}) for v in views(nid, t)]
    order = {"current": 0, "event": 0, "plan": 1, "past": 2}
    return sorted(out, key=lambda x: (order[x[1]["state"]], -x[1]["weight"], x[1]["family"] or "", x[0]))

def fmt(v):
    e = v["edge"]
    tags = [t for t in ({"past": "past", "plan": "PLAN"}.get(v["state"], ""), "prep" if e.get("layer") == "prep" else "",
                        when(e), e.get("plan") or "", e.get("note") or "") if t]
    return f"{'●' * v['weight'] or '·'} {v['family']}/{v['type']}" + (f" ({' · '.join(tags)})" if tags else "")

print(f"[after S{AT_N}{', with plans' if PLANS else ''}{', canon only' if NOPREP else ''}]")
if "--find" in args:
    q = opt("--find").lower()
    for n in G["nodes"]:
        hay = " ".join([n["id"]] + [str(a) for a in n.get("aliases", [])] + [str(n.get("summary", ""))]).lower()
        if q in hay:
            print("-", line(n["id"]))
elif "--path" in args:
    i = args.index("--path"); a, b = resolve(args[i + 1]), resolve(args[i + 2])
    dist, prev, pq = {a: 0}, {}, [(0, a)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b: break
        for v_ in ADJ.get(u, {}):
            vs = views(u, v_)
            if not vs: continue
            nd = d + 6 - max(x["weight"] for x in vs)
            if nd < dist.get(v_, 1e9):
                dist[v_], prev[v_] = nd, u; heapq.heappush(pq, (nd, v_))
    if b not in dist: sys.exit("No typed connection")
    chain = [b]
    while chain[-1] != a: chain.append(prev[chain[-1]])
    chain.reverse()
    for x, y in zip(chain, chain[1:]):
        v = views(x, y)[0]
        e = v["edge"] if v["forward"] else dict(v["edge"], **{"from": x, "to": y, "type": v["type"],
                                                             "form": TYPES.get(v["type"], {}).get("form", "verb")})
        print("-", sentence(e, v["state"]) + f" ({'●' * v['weight']})")
else:
    root = resolve(next(a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in VALUE)))
    print(line(root)); seen = {root}
    first = links(root)
    for t, v in first:
        print(f"  {fmt(v)}: {line(t)}"); seen.add(t)
    if DEPTH >= 2 and not (FAM or TYP):
        done = set()
        for t, v in first:
            if v["weight"] < 3 or v["state"] == "past" or t in done: continue
            done.add(t)
            nxt = [(t2, v2) for t2, v2 in links(t) if t2 not in seen and v2["weight"] >= 3]
            if nxt:
                print(f"\n  via {t}:")
                for t2, v2 in nxt[:8]:
                    print(f"    {fmt(v2)}: {t2}")
