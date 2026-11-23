---
name: post-session
description: Run the end-of-session sync for the Wilds of Ossë campaign. Reads the session's speaker-labelled Discord transcript (and the screen's Export, and Tom's corrections), writes what actually happened at the table into the Ossë vault as canon (session note, Session Log rows, state and location changes, new notes, revealed secrets, threads), marks plans played or overtaken, runs the build so impossible plans are pruned and the DM pages and codex are rebuilt, publishes the players' chronicle, then refreshes the names for the transcript bot. Use when Tom says the session is done, wrapped or over, "we just played", or asks to sync, update the lore or reconcile play against the vault.
---

# Ossë post-session sync

The rules are in `docs/osse/` (README first, then `notes.md` and `plans.md`). This skill is the order of work. Everything runs from this repo; the vault is read and written as files. Mind the two boundaries in `docs/osse/README.md`: the chronicle is a player screen, so it shows only what came out in play.

Sources: from S14 on, a Discord bot records the voice channel and gives a transcript labelled by speaker. Sessions up to S13 came from Notion AI summaries; their canon is already in the vault, so Notion is no longer read.

## Rules that never bend
- **Propose before writing.** Show Tom the whole proposal and wait for a clear yes. Then write, build, and report.
- **Canon comes only from play.** Only what the transcript records (or Tom's correction of what happened at the table) gets a session stamp. Nothing becomes canon because it was planned.
- **The table wins.** Tom's corrections beat the transcript: keep every detail he gives, terse, and add nothing he did not say.
- **Prep that play contradicts is a conflict.** Show both versions and their sources; Tom rules. Never fix it silently.
- **Direct tie test** for every line (`docs/osse/notes.md`).
- Tom often works by voice on his phone. Keep messages short and scannable; group questions into one numbered list.

## Step 1: Pick the session
The session is the one after the current session (`osse.py brief`), unless Tom named one. Get its transcript: the Discord bot's speaker-labelled export, as a file Tom gives or points to. If there is none, ask for it and stop. Also take the screen's Export if Tom gives it (what was reached, which clues were found, the fight).

Read the transcript yourself; there is no AI summary to lean on any more.
- **Speakers.** Map each speaker to a character with the `player` property of the pc notes (`osse.py card` on each PC). Tom is the DM: he narrates and voices every NPC, so name the NPC from context when he speaks in character. A line you cannot place goes to Tom as a question.
- **In play or out.** Table talk, rules talk and out-of-character jokes are not canon. When a line could be either, ask.
- **Spelling.** Speech-to-text garbles names. Match each to `Glossary.md` and `osse.py find`; list the ones you had to guess.
- Write the session's own summary for the session note (`summary`, What happened, What changed) from the transcript.

## Step 2: Read what was planned
`python3 tools/osse/osse.py brief` and `python3 tools/osse/osse.py plans`: every `ready` plan, and every live plan aimed at this session or earlier. `osse.py card "<plan>"` for each one that matters. `osse.py card NAME` for each entity the summary touches.

## Step 3: Classify
- **Event**: happened, now canon.
- **Divergence**: play went where the plan did not. The plan is overtaken.
- **Conflict**: play contradicts prep. Needs a ruling.
- **New entity**: first appeared. Create a note (check `osse.py find` first), or promote a prep or draft note (`first_seen`, `stage: canon`).
- **Reveal**: the party learned a secret. Set `revealed`, change matching `prep` links to the session stamp.
- **Summary error**: the summary garbled it. Correct it; do not carry it forward.
Then two checks: every load-bearing clue (the screen's Export says which were found) (carry the ones that did not land as `not landed` on the thread), and the ripple check (which notes still assert the old state of anything that changed).

## Step 4: Plans
For each plan from Step 2, propose one of:
- **played**: `status: played`, `played: S<n>`, a Log line pointing to the session note. Canon comes from Step 3, not from the plan.
- **partly played**: mark it played and propose a new draft for the part still ahead.
- **overtaken**: `status: pruned`, `pruned: S<n>`, `pruned_by: "overtaken by S<n>: <why>"`. Suggest the requirement that would have caught it.
- **untouched**: stays live; propose a new `target` or `dropped`.

## Step 5: Propose
Grouped by note, phone-sized:
- The new session note (`Sessions/S<n> - <title>.md`), in full.
- Each entity: the Session Log row, property changes quoted, link lines to add or end.
- New notes, with their front matter.
- Plans: played, overtaken, retargeted.
- Conflicts for a ruling. Clues that did not land. Anything held back.
Then preview the automatic pruning: `python3 tools/osse/build.py --dry` with one `--assume "Note: key=value"` per proposed property change, and list what it would prune and why. Link changes cannot be assumed; reason those out from the plans' `## Requires`. Tom should never be surprised by what the build drops.

## Step 6: Write, build, report
On approval, write every change with a short script (never re-type a note). Run `python3 tools/osse/build.py` (it also rebuilds the `vault/` DM pages). Fix every PROBLEM line. Commit `vault/` and push. Report: notes created and updated, plans played, **plans pruned by the build (with reasons)**, stale plans, and the judgment calls (`osse.py plans --checks`) for next time.

## Step 7: Players' chronicle
Follow the `chronicle` skill: write `Chronicle/S<n> - <title>.md` with `tools/chronicle.py note`, export, check, commit and push. Only what the table saw; no secrets, plans or prep. Add any new quest line to `Chronicle/Quest lines.md`.

## Step 8: Names for the transcript bot
Run this again before each session, after prep (see `docs/osse/README.md`, Before a session).
The build rewrites the vault's `Glossary.md`: every proper noun in canon and prep. If the transcript bot takes a word list or custom vocabulary, give it the names from `Glossary.md` (additions only; never remove or respell). Until the bot is set up, `Glossary.md` is only the spelling reference for Step 1.

## Output style
Plain prose and short bullets. No em dashes. No "it's not X, it's Y". Never claim a write landed without checking it.
