---
name: paths
description: Bring Tom's Paths ahead planning boards into the Ossë vault. Use when Tom asks to read, sync, formalize or "bring in" the board, the paths, his branches or the cards he added on the Paths ahead page.
---

# Bring the Paths ahead boards into the vault

Tom plans on the Paths ahead page (`vault/paths.html`): he places plans into session columns, draws links and adds cards. The page saves to the Gus relay; the vault does not change until this skill runs. Rules: `docs/osse/branching.md` and `docs/osse/plans.md`.

## Step 1: Read
`python3 tools/osse/paths_sync.py show` (add a board name to see one). It prints, per board:
- **set target**: a plan moved to another session column, or placed from the tray. `Later` means an empty target.
- **add for**: a plan placed on a board it is not tied to.
- **left in the tray**: a plan whose vault target Tom did not place. Ask before clearing that target.
- **NEW CARD**: Tom's card, with its kind, column, text and links.
- **NEW LINK**: Tom's link between two vault plans, with its label.

## Step 2: Turn it into vault changes
- A NEW CARD becomes a plan note in `Plans/`, written with a short script, following `docs/osse/plans.md`: `stage: draft`, `status: draft`, `kind:` from the card (a `note` card becomes the kind its text describes; ask if unclear), `target:` from its column, `for:` the board's character (not for Around the party), a one-line `summary`, `## Idea` from the card text in Tom's words, tightened.
- Links into a card or between plans:
  - from a decision: an `## Options` line in the decision, `- [[Plan]] · label`;
  - labelled "then" or unlabelled, between scenes: `plan: [[Earlier]]` in the later plan's `## Requires`;
  - from Now: no requirement; it only means "from where they stand".
  - any other label: work out what must be true and write it as a requirement (`hidden:`, `alive:`, `met:`…), or `check:` when no rule can test it.
- Add the `## Requires` lines the idea needs (secrets hidden, people alive) and `## Links` for what it would change.
- Never write canon. Never copy a plan into an entity note.

## Step 3: Propose, then write
Show Tom the new and changed plans, phone-sized, grouped by board. On approval: write them, run `python3 tools/osse/build.py`, fix every problem it prints.

## Step 4: Swap cards for plans, tidy, publish
- For each card that became a plan: `python3 tools/osse/paths_sync.py adopt BOARD CARD_ID "Plan name"`. The card keeps its place on the board.
- `python3 tools/osse/paths_sync.py tidy` drops Tom's links that the vault now holds.
- Commit `vault/` and push, so the page shows the new plans.
- Report what changed, and any plan the build pruned.

`python3 tools/osse/paths_sync.py export DIR` writes each board as a `.canvas` file Obsidian can open, if Tom asks.
