---
name: session-screen
description: Build and publish the game master screen page for a Wilds of Ossë session (screen/sNN.html), from that session's plan. Use when asked to make, update or publish a session screen, dashboard or DM screen.
---

# Session screen

One self-contained page per session, `screen/sNN.html`, run in a single 5e.tools DM Screen pane (Embed) on a vertical monitor. `screen/s13.html` is the reference build. Start every new screen as a copy of the most recent one.

## 1. Get the plan first

The story comes from the session plan (the Notion session page, or the "Prep Review" page exported from it). Never invent scenes, NPCs, clues or lines. If the plan is not in the conversation or on disk, ask for it and stop.

From the plan, pull:

| Plan section | Becomes |
|---|---|
| Movements (scene, type, minutes, lead, jobs, flagged beats, pen questions) | `MOVES`, and the tabs |
| Roll call or cast state | `ROLL` |
| Finds, rolls, what each gives, who | `EVID` |
| Initiative carried over | `INIT` |
| NPC lines by beat | `VOICES`, and the speech view for set pieces |
| Do not reveal, offscreen clocks | `SECRETS`, `CLOCKS` |
| Creatures on stage, and the four PCs | `SB` (stat blocks) |

## 2. Shape the screen around the story

- One movement per scene. Each names its lead PC, a job for every other PC, the flagged beats, and the pen questions.
- Group movements into two to four tabs by phase. `MVTAB` maps each movement to its tab, so Next in Spotlight changes tab by itself.
- Pick each tab's panels by what the scene is:

| Scene type | Panels |
|---|---|
| Combat | Stat blocks, a tracker for the main foe (attack bonus, HP, typed damage, quick buttons), Initiative, Voices, Roll call |
| Roleplay, investigation | Roll call, Evidence (full width), Voices, Sealed |
| Speeches, endings | Speech view in large type with fill-ins from Roll call, Roll call, Evidence, Sealed |

- Spotlight is the top row of every tab. Sealed is at the bottom and closed.
- Retire panels the session does not need. Add a bespoke one when a scene has its own mechanic (S13: The Hand).
- Every panel also works alone at `#panel=<name>`, and each tab at `#tabN`.
- Initiative is editable at the table: adjust a roll, remove a name, add one from the cast or by typing. Keep that.
- Keep the Export button. Its text must list every beat, clue, roll call state and the fight as plain Markdown, flag what was not reached or not found, and end with the board state so it can be restored. Tom gives it to Claude for the post-session sync, with the summary and transcript.
- Keep the iPad view (`#ipad`, and automatic on a touch device in landscape): Spotlight on the left, one view at a time on the right, chosen per tab in `TV`. Combat pairs the foe tracker with Initiative. Built for 1024 by 740, tap only: targets 44px or larger, a number pad instead of a text field, nothing that needs hover.

## 3. Stat blocks

Player characters: carry the blocks forward from the last screen and update them from the current sheets. The **Tonight** call-out lists only what matters this session: defense bonus, the spells, items and features likely to come up, and anything the story hands them.

NPCs: every move must be a published mechanic, or a baseline rule with new flavour. Players should recognize what hit them.

- Start from the closest published block (gladiator, warlord, assassin, a class feature, a spell) and rename. Check the wording against 5e.tools data, not memory: `https://raw.githubusercontent.com/5etools-mirror-3/5etools-src/main/data/bestiary/bestiary-<source>.json`.
- End each entry with its source in double braces, for example `{{Command Ally, as the warlord.}}`. The page shows it as a small note.
- Check the math: proficiency bonus fits the challenge rating; attack bonus is ability modifier plus proficiency; save DC is 8 plus modifier plus proficiency; hit points match the hit dice.
- Table rules: normal attack rolls against AC. Do not use player-rolled defense. Show damage in stat-block form, the average with the dice in brackets, for example 14 (1d6 + 4 piercing plus 2d6 poison). Tom rolls damage for named NPCs such as Corvane and Cassian.
- In a PC's **Tonight** call-out, give the AC and the roll the main foe needs to hit it.
- Casters follow their class: only spells on the class or subclass list, no more spells than that level knows, and the right slots. A warlock has few slots, all at the top level, back on a short rest. Scale effects to the slot level used.
- Session rulings go in **Tonight**, written as rulings, with the baseline rule they bend.
- Marquis Corvane is a warlock, Pact of the Blade, with a fire-leaning Fiend spell list. Keep him that way unless told otherwise.

## 4. Design rules

- One file, no outside fonts, scripts or images. State lives in `localStorage` under a key unique to the session (`osse-sNN-v1`), so panels and tabs stay in step.
- Built for one pane at about 1080 by 1800. The Spotlight row fits its content. Nothing the game master needs in the moment may sit behind a scroll in Spotlight.
- The main control of a panel sits in its header and never scrolls away. Next names where it goes.
- Small cells get the compact view (`mini`): names and titles only.
- Anything that wipes state needs a second tap. Numbers that change often get a typed field as well as buttons.
- Keep the dark palette, PC colours and type scale from the reference build. Body text 15px or larger.
- Canadian English. No em dashes.

## 5. Test

Run the `screen` preview server (`.claude/launch.json`) and check in the browser:

1. Each tab at 1080 by 1800: nothing cut off in Spotlight, every panel readable.
2. Spotlight and one other panel alone at 520 by 420.
3. The iPad view at 1024 by 740: every tab and view, the number pad, no control under 44px.
4. Click through: Next across all movements, damage entry, roll call taps, evidence ticks, sealed open and close, every stat block and voice.
5. No console errors, and no `{{` left showing.

## 6. Publish

1. Add a section for the session to `screen/README.md`. Base address: `https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/sNN.html`.
2. Run the pre-commit check from `CLAUDE.md`. If the build only changed timestamps in `wilds-of-osse.json`, do not commit that file.
3. Commit to main and push.
4. Wait for GitHub Pages, then confirm the base address returns 200 and matches the committed file.
5. Tell Tom the address, what he will see, and anything he must do. Old test state clears with Reset, tapped twice.
