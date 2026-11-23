---
name: chronicle
description: Add or update a session in the players' chronicle (chronicle/ on the site), the player-facing page with each session's summary, quest lines, NPCs and items. Use when Tom asks to add a session to the chronicle, publish a recap for the players, or fix something players read there.
---

# The players' chronicle

The page is `chronicle/index.html`; it reads `chronicle/chronicle.json` and the homebrew file for item cards. The JSON is generated. Never edit it by hand.

## Where the truth lives

```
Notion player summary ──(for now)──▶ Ossë vault: Chronicle/S<n> - <title>.md ──export──▶ chronicle/chronicle.json ──▶ site
                                     Ossë vault: Chronicle/Quest lines.md     ─┘
```

- The Ossë vault (iCloud Obsidian, game master only) is canon. Its `Chronicle/` folder is the one part written for the players, and the export reads nothing else, so secrets and plans cannot reach the public site.
- For now each session's recap is pulled from its Notion player summary into the vault. Once the vault's own session notes carry everything, write the chronicle note from the vault session note instead (only what the table saw).
- A `[[link]]` in a chronicle note shows as **bold** on the site: that is how names with a vault entry are marked. Only the shown text is published, never the link target.

## Add a session

1. Get the recap as JSON in the session scratchpad (the shape is in the docstring of `tools/chronicle.py`): from the Notion page (the `<meeting-notes-section-summary>` part only; the notes part can hold the previous session), using the rules below.
2. `python3 tools/chronicle.py note <file.json>` writes `Chronicle/S<n> - <title>.md` in the vault and links the first mention of each name per paragraph. It refuses to replace an existing note (Tom may have edited it); add `--force` only when Tom asked to rebuild it.
3. New quest line? Add it to `Chronicle/Quest lines.md`: a `### Name` heading, one short sentence on what the quest is for (player knowledge only), and `- also called: other name; other name` for wordings the summaries use.
4. `python3 tools/chronicle.py export`, then fix every `!` line it prints.
5. Check the page locally (`hub` preview, `/chronicle/`), at desktop and phone width.
6. Run the repo check, commit `chronicle/chronicle.json`, push, confirm live.

## Text rules (players read this)
- Only what happened at the table. Nothing from prep, plans, secrets or the vault's other notes.
- Character names only, never the players' real names.
- No em dashes, no "it's not X, it's Y", Canadian spelling, glossary spelling for every proper noun (`Glossary.md` in the vault).
- No meta talk about recordings or transcripts.
- Quest status: `new`, `changed`, `none` (no progress, shown dimmed and folded), `resolved`.
- NPCs: only those present in play that session. `title`, `faction`, `role`, `state` (for example Deceased), `new: yes` on first appearance.
- Items: `homebrew:` names the exact item in `src/items.json` so the page can show its card. An item with no homebrew entry shows only its session note; add a homebrew entry in `src/items.json` if Tom wants a card.
