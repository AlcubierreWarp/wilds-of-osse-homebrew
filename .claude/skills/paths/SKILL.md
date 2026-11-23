---
name: paths
description: Bring Tom's Paths ahead planning boards into the Ossë vault. Use when Tom asks to read, sync, formalize or "bring in" the board, the paths, his branches or the cards he added on the Paths ahead page.
---

# Bring the Paths ahead boards into the vault

Tom plans on the Paths ahead page (`vault/paths.html`): one tab per session; he places plans on a session's canvas, draws links, adds, edits and deletes cards, and drops plans. The page saves to the Gus relay; the vault does not change until this skill runs. Rules: `docs/osse/branching.md` and `docs/osse/plans.md`.

## Step 1: Read
`python3 tools/osse/paths_sync.py show` (add a board name to see one). Everything has one copy and is listed once, under the first board it is on:
- **set target**: a plan moved to another session tab, or placed from the tray. `Later` means an empty target.
- **add for**: a plan placed on a board it is not tied to.
- **left in the tray**: a plan whose vault target Tom did not place. Ask before clearing that target.
- **NEW CARD**: Tom's card, with its kind, session, text and links; for a scene, where, who is present and the boards it is on; for a clock, its progress; the scene it sits in.
- **set scene**: a plan Tom placed inside a scene.
- **EDITED**: Tom changed a plan's kind, summary or idea, or left a note to Claude.
- **DROP**: Tom dropped a plan.
- **NEW LINK**: Tom's link between two vault plans, with its label.
- **Running order**: each session's scenes, in the order Tom set on the Session plan. Nothing goes into the vault; when building that session's screen (the `session-screen` skill), run the scenes in this order.

## Step 2: Turn it into vault changes
- A scene card becomes a `kind: scene` plan with `where:` (a [[link]] when the vault has the place; plain text otherwise, and ask Tom whether it needs a place note) and `present:` (a list; [[links]] for people in the vault, plain text for the rest). Write the scene first, then the cards inside it with `scene: "[[Scene]]"`.
- A clock card becomes a `kind: clock` plan with `clock: filled/segments`; its text is what happens when it fills.
- A NEW CARD becomes a plan note in `Plans/`, written with a short script, following `docs/osse/plans.md`: `stage: draft`, `status: draft`, `kind:` from the card (a `note` card becomes the kind its text describes: usually a beat; ask if unclear), `target:` from its column, `for:` the board's character (not for Around the party; not for a scene whose `present:` already names them), a one-line `summary`, `## Idea` from the card text in Tom's words, tightened.
- Links into a card or between plans:
  - from a decision: an `## Options` line in the decision, `- [[Plan]] · label`;
  - labelled "then" or unlabelled, between scenes: `plan: [[Earlier]]` in the later plan's `## Requires`;
  - from Now: no requirement; it only means "from where they stand".
  - any other label: work out what must be true and write it as a requirement (`hidden:`, `alive:`, `met:`…), or `check:` when no rule can test it.
- Add the `## Requires` lines the idea needs (secrets hidden, people alive) and `## Links` for what it would change.
- An EDITED plan: write the new `kind:`, `summary:`, `where:`, `present:` and `clock:` as given. Rewrite `## Idea` from his text, turning names back into `[[links]]`; keep any links he removed only if the idea still needs them. Do what his note asks. If it asks for a new name, never rename the file: add the new name to `aliases` and ask Tom. Add a log line, `- S<cur>: idea revised on Paths ahead.`
- A DROP: set `status: dropped` and add a log line. Never delete the note.
- A link from the start of a session (`the start of S15`): no requirement; it means "from where they stand at the start of that session".
- Never write canon. Never copy a plan into an entity note.

## Step 3: Propose, then write
Show Tom the new and changed plans, phone-sized, grouped by board. On approval: write them, run `python3 tools/osse/build.py`, fix every problem it prints.

## Step 4: Swap cards for plans, tidy, publish
- For each card that became a plan: `python3 tools/osse/paths_sync.py adopt CARD_ID "Plan name"`. It keeps its place on every board.
- `python3 tools/osse/paths_sync.py tidy` drops Tom's links that the vault now holds, and plans no longer live.
- `python3 tools/osse/paths_sync.py settle` clears the edits and drops the vault now holds, so the cards show the vault's text again.
- Commit `vault/` and push, so the page shows the new plans.
- Report what changed, and any plan the build pruned.

`python3 tools/osse/paths_sync.py export DIR` writes each board as a `.canvas` file Obsidian can open, if Tom asks.
