#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["mlx-whisper>=0.4.2", "numpy"]
# ///
"""Turn a Craig recording of the Wilds of Ossë voice channel into a transcript labelled by speaker.
  uv run tools/transcript.py                     newest Craig zip in Downloads (Mac or iCloud), for the next session
  uv run tools/transcript.py ZIP --session 14    a given zip or extracted folder, for a given session
  uv run tools/transcript.py --session test      a test run (writes test.txt)
  uv run tools/transcript.py --session 14 --render   rewrite the file from the cache (after fixing speakers.json)
Craig records one track per person, so each line's speaker is exact. Whisper (large-v3-turbo, 4-bit, on this Mac) hears
only the stretches where someone talks, prompted with names from the vault's Glossary.md, then a cleanup pass
fixes near-misses against the whole Glossary and lists them at the end of the file.

Everything lands outside this public repository, in TRANSCRIPTS (iCloud Drive/Ossë transcripts):
  S14.txt           the transcript: one line per utterance, "[01:12:34] Peter (Gabriele): we go to the docks"
  speakers.json     Discord username -> player first name; the pc notes' `player` property gives the character
  .cache/S14/       per-track results, so a re-run or --render does not transcribe again
Set OSSE_TRANSCRIPTS to write elsewhere."""
import argparse, difflib, glob, hashlib, json, os, re, subprocess, sys, tempfile, time, zipfile
from datetime import date, datetime

VAULT = os.environ.get("OSSE_VAULT") or os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ossë")
TRANSCRIPTS = os.environ.get("OSSE_TRANSCRIPTS") or os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Ossë transcripts")
DOWNLOADS = ["~/Downloads", "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads"]
MODEL = "mlx-community/whisper-large-v3-turbo-q4"
DM = "Tom"
RATE = 16000
PAD = 0.25            # seconds kept either side of speech
PAUSE = 1.2           # a pause this long starts a new line
PIECE = 150           # seconds of speech handed to Whisper at a time (keeps memory low on 8 GB)
CACHE_MB = 256        # cap on MLX's memory cache; without it an 8 GB Mac swaps and slows to a crawl
PROMPT_CHARS = 650    # Whisper reads about 224 tokens of prompt
AUDIO = (".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".mp3")


def say(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------- the vault: names, players, sessions ----------
def split_top(s):
    """Split on commas that are not inside parentheses."""
    out, depth, cur = [], 0, ""
    for ch in s:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def glossary():
    """[(category, name, [aliases])] from Glossary.md."""
    path = os.path.join(VAULT, "Glossary.md")
    names = []
    if not os.path.exists(path):
        say(f"No Glossary.md in the vault ({path}); transcribing without names.")
        return names
    for line in open(path, encoding="utf-8"):
        m = re.match(r"- \*\*(.+?):\*\*\s*(.+)", line.strip())
        if not m:
            continue
        for item in split_top(m.group(2)):
            n = re.match(r"([^(]+?)\s*(?:\((.*)\))?$", item)
            if n:
                names.append((m.group(1), n.group(1).strip(), split_top(n.group(2) or "")))
    return names


def front(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    props = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M)) if m else {}
    return props, text


def characters(names):
    """player first name -> character's short name, from the pc notes (Gabriele d'Avidicci -> Gabriele)."""
    aliases = {n: a for _, n, a in names}
    out = {}
    for path in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        props, _ = front(path)
        if props.get("type") == "pc" and props.get("player"):
            name = os.path.splitext(os.path.basename(path))[0]
            words = name.split()
            short = [a for a in aliases.get(name, []) if " " not in a and a in words]
            out[props["player"].strip()] = name if len(words) == 1 else (short[0] if short else name)
    return out


def sessions():
    """[(number, path)] of session notes, oldest first."""
    found = []
    for path in glob.glob(os.path.join(VAULT, "Sessions", "S*.md")):
        m = re.match(r"S(\d+)\b", os.path.basename(path))
        if m:
            found.append((int(m.group(1)), path))
    return sorted(found)


ORDER = {"People": 0, "Factions & peoples": 1, "Places": 2}


def prompt(names, pcs):
    """Whisper's prompt: the party, then the names the last two sessions use most, then the rest, within its budget.
    Each name goes in its shortest form that still holds the hard spelling (Seranthis, not Kingdom of Seranthis)."""
    recent = " ".join(open(p, encoding="utf-8").read() for _, p in sessions()[-2:])

    def short(n, aliases):
        if not re.match(r"(Kingdom of|House|Embassy of|The)\b", n):
            return n
        words = [a for a in aliases if a in n and len(a) >= 4 and not a.lower().startswith("the ")]
        return min(words, key=len) if words else n

    def uses(n, aliases):
        return sum(recent.count(x) for x in {n, *aliases} if len(x) >= 3)

    proper = [x for x in names if x[0] in ORDER or all(w[:1].isupper() for w in x[1].split())]
    ranked = sorted(proper, key=lambda x: (-uses(x[1], x[2]), ORDER.get(x[0], 3)))
    first = list(pcs.values())
    seen = [short(n, a) for c, n, a in ranked if uses(n, a)]
    rest = [short(n, a) for c, n, a in ranked if c in ORDER and not uses(n, a)]
    picked, size = [], 0
    def inside(x, y):
        return x != y and re.search(r"\b" + re.escape(x) + r"\b", y)

    for n in first + seen + rest:
        if n in picked or any(inside(n, p) for p in picked) or size + len(n) + 2 > PROMPT_CHARS:
            continue
        for p in [p for p in picked if inside(p, n)]:
            picked.remove(p); size -= len(p) + 2
        picked.append(n); size += len(n) + 2
    return "Wilds of Ossë, a Dungeons & Dragons session. Names: " + ", ".join(picked) + ".", picked


# ---------- the recording ----------
def newest_zip():
    found = [p for d in DOWNLOADS for p in glob.glob(os.path.join(os.path.expanduser(d), "*.zip"))
             if "craig" in os.path.basename(p).lower()]
    return max(found, key=os.path.getmtime) if found else None


def open_recording(src, work):
    """Folder holding the tracks (extracting a zip into work)."""
    if os.path.isdir(src):
        return src
    with zipfile.ZipFile(src) as z:
        z.extractall(work)
    return work


def tracks(folder):
    out = []
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith(AUDIO) and not f.startswith("."):
                out.append(os.path.join(root, f))
    return out


def username(path, info=""):
    """The Discord username of a track. Craig names files 1-someone.flac; info.txt lists the exact names in the same order."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r"(\d+)[-_ ](.*)$", stem)
    listed = re.findall(r"^\t(.+?)(?:#\d+)? \(\d+\)\s*$", info.split("Tracks:", 1)[1], re.M) if "Tracks:" in info else []
    if m and 0 < int(m.group(1)) <= len(listed):
        return listed[int(m.group(1)) - 1]
    return m.group(2) if m else stem


def recorded(info):
    """When the recording started, in local time, from info.txt."""
    m = re.search(r"Start time:\s*(\S+)", info)
    if not m:
        return ""
    when = datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).astimezone()
    return when.strftime("%Y-%m-%d %H:%M")


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def speech(path, total):
    """[(start, end)] seconds where the track is not silent. Discord sends audio only while someone talks."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "silencedetect=noise=-45dB:d=0.4",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    regions, start = [], 0.0
    for kind, t in re.findall(r"silence_(start|end): (-?[\d.]+)", err):
        t = max(0.0, float(t))
        if kind == "start":
            if t > start:
                regions.append((start, t))
        else:
            start = t
    if start < total:
        regions.append((start, total))
    merged = []
    for a, b in regions:
        a, b = max(0.0, a - PAD), min(total, b + PAD)
        if b - a < 0.3:
            continue
        if merged and a - merged[-1][1] < 0.3:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def pieces(regions):
    """Group regions into pieces of about PIECE seconds of speech."""
    out, cur, size = [], [], 0.0
    for a, b in regions:
        cur.append((a, b)); size += b - a
        if size >= PIECE:
            out.append(cur); cur, size = [], 0.0
    if cur:
        out.append(cur)
    return out


def packed(path, regions):
    """The piece's speech stitched together, with a map from packed time back to the recording's time."""
    import numpy as np
    parts, mapping, at = [], [], 0.0
    gap = np.zeros(int(0.4 * RATE), dtype=np.float32)
    for a, b in regions:
        raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", path,
                              "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"], capture_output=True).stdout
        clip = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        mapping.append((at, at + len(clip) / RATE, a))
        parts += [clip, gap]
        at += (len(clip) + len(gap)) / RATE
    return (np.concatenate(parts) if parts else np.zeros(0, np.float32)), mapping


def real_time(t, mapping):
    """Packed time to recording time. A time in the gap between two stretches belongs to the next one."""
    for p0, p1, a in mapping:
        if t <= p1:
            return a + max(0.0, t - p0)
    p0, _, a = mapping[-1]
    return a + (t - p0)


JUNK = re.compile(r"^((thank you|thanks) (so much )?for watching|please subscribe)[.!]?$", re.I)   # Whisper invents these


def transcribe_track(path, cache, text_prompt):
    """The cache files holding one track's [start, end, word] lists, one per piece. They are keyed to the audio and the
    settings, so a new recording or a changed setting never reuses old results."""
    import mlx.core as mx
    import mlx_whisper
    mx.set_cache_limit(CACHE_MB * 2**20)
    with open(path, "rb") as f:
        key = hashlib.sha256(f.read() + f"{MODEL} {PIECE} {text_prompt}".encode()).hexdigest()[:12]
    total = duration(path)
    regions = speech(path, total)
    talk = sum(b - a for a, b in regions)
    say(f"  {username(path)}: {talk / 60:.0f} min of speech in {total / 60:.0f} min")
    parts, t_start, todo = [], time.time(), pieces(regions)
    for i, piece in enumerate(todo):
        part = os.path.join(cache, f"{key}.{i:03d}.json")
        parts.append(os.path.basename(part))
        if os.path.exists(part):
            continue
        audio, mapping = packed(path, piece)
        t0 = time.time()
        result = mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, language="en", initial_prompt=text_prompt,
                                        condition_on_previous_text=False, word_timestamps=True, verbose=None,
                                        hallucination_silence_threshold=2.0)
        got = []
        for seg in result.get("segments", []):
            if seg.get("no_speech_prob", 0) > 0.7 and seg.get("avg_logprob", 0) < -1.0:
                continue
            if JUNK.match(seg.get("text", "").strip()) and seg.get("end", 0) - seg.get("start", 0) < 2:
                continue
            for w in seg.get("words", []):
                got.append((round(real_time(w["start"], mapping), 2), round(real_time(w["end"], mapping), 2), w["word"]))
        with open(part + ".new", "w") as f:
            json.dump(got, f)
        os.replace(part + ".new", part)
        mx.clear_cache()
        say(f"    piece {i + 1} of {len(todo)}: {sum(b - a for a, b in piece) / 60:.1f} min of speech in {time.time() - t0:.0f} s")
    say(f"    done in {(time.time() - t_start) / 60:.1f} min")
    return parts


# ---------- the transcript ----------
def utterances(words):
    """Group one speaker's words into lines at each pause."""
    out, cur = [], []
    for w in sorted(words):
        if cur and (w[0] - cur[-1][1] >= PAUSE or (len(cur) > 60 and cur[-1][2].rstrip().endswith((".", "?", "!")))):
            out.append(cur); cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [(u[0][0], "".join(w[2] for w in u).strip()) for u in out]


def stamp(t):
    t = int(round(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def fix_names(lines, names):
    """Correct near-miss names against the whole Glossary. Skips real English words. Returns lines, fixed, unsure."""
    try:
        english = {w.strip().lower() for w in open("/usr/share/dict/words")}
    except OSError:
        english = set()
    vocab, exact = {}, set()
    for _, n, aliases in names:
        for name in [n] + aliases:
            for word in re.findall(r"[A-Z][\w'’-]{3,}", name):
                exact.add(word.lower())
                if word.lower() not in english:   # never pull a word toward ordinary English (Where, Constable)
                    vocab.setdefault(word.lower(), word)
    keys = list(vocab)
    fixed, unsure, memo = {}, {}, {}

    def best(word):
        low = re.sub(r"['’](s|ll|re|ve|d|m|t)$", "", word.lower())
        if low in memo:
            return memo[low]
        hit = None
        if low not in exact and low not in english and len(low) >= 4:
            match = difflib.get_close_matches(low, keys, n=1, cutoff=0.72)
            if match:
                hit = (vocab[match[0]], difflib.SequenceMatcher(None, low, match[0]).ratio())
        memo[low] = hit
        return hit

    def swap(m):
        word = m.group(0)
        hit = best(word)
        if not hit:
            return word
        target, ratio = hit
        if ratio >= 0.84:
            fixed[(word, target)] = fixed.get((word, target), 0) + 1
            return target + word[len(re.sub(r"['’](s|ll|re|ve|d|m|t)$", "", word)):]
        unsure[(word, target)] = unsure.get((word, target), 0) + 1
        return word

    # Proper names of two or more words keep the Glossary's capitals ("the glowing goat" -> "the Glowing Goat").
    small = {"of", "the", "de", "and", "d'Avidicci"}
    multi = set()
    for _, n, aliases in names:
        for x in [n] + aliases:
            x = re.sub(r"^[Tt]he ", "", x)
            if " " in x and all(w[:1].isupper() or w in small for w in x.split()):
                multi.add(x)
    caps = [(re.compile(r"\b" + re.escape(x) + r"\b", re.I), x) for x in sorted(multi, key=len)]

    def recase(text):
        for rx, x in caps:
            text = rx.sub(lambda m: x, text)
        return text

    out = [(t, who, recase(re.sub(r"\b[A-Z][\w'’-]{3,}", swap, text))) for t, who, text in lines]
    return out, fixed, unsure


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording", nargs="?", help="Craig zip or extracted folder (default: newest Craig zip in Downloads)")
    ap.add_argument("--session", help="session number, or a word such as test (default: the next session)")
    ap.add_argument("--render", action="store_true", help="only rewrite the transcript from the cache")
    ap.add_argument("--force", action="store_true", help="replace an existing transcript")
    args = ap.parse_args()

    done = sessions()
    session = args.session or str((done[-1][0] if done else 0) + 1)
    label = f"S{session}" if session.isdigit() else session
    os.makedirs(TRANSCRIPTS, exist_ok=True)
    out_path = os.path.join(TRANSCRIPTS, f"{label}.txt")
    cache = os.path.join(TRANSCRIPTS, ".cache", label)
    if os.path.exists(out_path) and not (args.force or args.render):
        sys.exit(f"{out_path} already exists. Pass --force to replace it, or --render to rewrite it from the cache.")

    names = glossary()
    pcs = characters(names)
    text_prompt, prompted = prompt(names, pcs)
    speakers_path = os.path.join(TRANSCRIPTS, "speakers.json")
    speakers = json.load(open(speakers_path)) if os.path.exists(speakers_path) else {}

    os.makedirs(cache, exist_ok=True)
    meta_path = os.path.join(cache, "tracks.json")
    if args.render:
        if not os.path.exists(meta_path):
            sys.exit(f"Nothing cached for {label}; run without --render first.")
        meta = json.load(open(meta_path))
    else:
        src = args.recording or newest_zip()
        if not src or not os.path.exists(src):
            sys.exit("No Craig recording found. Download the FLAC multi-track zip from Craig's link, or pass its path.")
        say(f"Recording: {src}")
        with tempfile.TemporaryDirectory() as work:
            folder = open_recording(src, work)
            found = tracks(folder)
            if not found:
                sys.exit("No audio tracks in the recording.")
            info = [p for p in glob.glob(os.path.join(folder, "**", "info.txt"), recursive=True)]
            notes = open(info[0], encoding="utf-8", errors="replace").read() if info else ""
            meta = {"recorded": recorded(notes), "tracks": []}
            say(f"Transcribing {len(found)} tracks with {MODEL}")
            for path in found:
                parts = transcribe_track(path, cache, text_prompt)
                meta["tracks"].append({"file": os.path.basename(path), "user": username(path, notes), "parts": parts})
            json.dump(meta, open(meta_path, "w"), indent=1)

    lines, labels, unknown = [], [], []
    for tr in meta["tracks"]:
        user = tr["user"]
        player = speakers.get(user) or speakers.get(user.lower())
        if not player:
            unknown.append(user)
            speakers.setdefault(user, "")
            who = user
        elif player == DM:
            who = f"{DM} (DM)"
        else:
            who = f"{player} ({pcs[player]})" if player in pcs else player
        labels.append(who)
        words = []
        for part in tr["parts"]:
            words += [tuple(w) for w in json.load(open(os.path.join(cache, part)))]
        lines += [(t, who, text) for t, text in utterances(words) if text]
    lines.sort(key=lambda x: x[0])
    lines, fixed, unsure = fix_names(lines, names)
    json.dump(speakers, open(speakers_path, "w"), indent=1, ensure_ascii=False)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Wilds of Ossë, {label} transcript\n")
        f.write(f"# Recorded by Craig {meta['recorded']}, transcribed {date.today().isoformat()} with {MODEL.split('/')[-1]}\n")
        f.write(f"# Speakers: {', '.join(labels)}\n")
        if unknown:
            f.write(f"# Unknown speakers (add them to speakers.json, then --render): {', '.join(unknown)}\n")
        f.write(f"# Names prompted: {', '.join(prompted)}\n")
        f.write("# Times are from the start of the recording. Tom voices every NPC; the speaker is who talked.\n\n")
        for t, who, text in lines:
            f.write(f"[{stamp(t)}] {who}: {text}\n")
        if fixed:
            f.write("\n# Names corrected: " + "; ".join(f"{a} -> {b} ({n}x)" for (a, b), n in sorted(fixed.items())) + "\n")
        if unsure:
            f.write("# Names to check: " + "; ".join(f"{a} -> {b}? ({n}x)" for (a, b), n in sorted(unsure.items())) + "\n")
    say(f"Wrote {out_path}: {len(lines)} lines")
    if unknown:
        say(f"Unknown speakers: {', '.join(unknown)}. Fill them in {speakers_path} (player first name, or {DM}), then --render.")


if __name__ == "__main__":
    main()
