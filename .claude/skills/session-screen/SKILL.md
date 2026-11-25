---
name: session-screen
description: Build and publish the game master screen page for a Wilds of Ossë session (screen/sNN.html, with an iPad layout and a tall 1080p layout), from that session's plan. Use when asked to make, update or publish a session screen, dashboard or DM screen.
---

# Session screen

One self-contained page per session, `screen/sNN.html`, with two layouts of the same board:

| Layout | Address | Device |
| --- | --- | --- |
| iPad | `screen/sNN.html#ipad` | iPad in landscape, 1024 by 740, tap only |
| Tall | `screen/sNN.html#tall` | the vertical 1080p monitor, 1080 by 1920, browser full screen |

Both follow the iPad layout: Spotlight plus one view at a time. On the iPad, Spotlight sits on the left and the view on the right; on the tall screen, Spotlight sits on top and the view fills the rest. The look is the table hub's (`index.html`): its palette, its fonts and its gold-on-dark panels. Start a new screen from the most recent one built to this standard; until there is one, take the iPad view of `screen/s13.html` for the structure and the hub for the look.

The hub's game master section finds the screen by itself (see step 6). Tom runs combat in Roll20 and talks in Discord voice; the screen is his notes and trackers, never a battle map.

## 1. Get the plan first

The story comes from Tom's plan for the session: the plans marked `ready` for it in the Ossë vault (`python3 tools/osse/osse.py plans`, then `card` on each), and any prep Tom gives in the conversation. Look up who and what is involved with `osse.py brief`, `card` and `find`. Run the scenes in the running order Tom set in the Session planner (`python3 tools/osse/paths_sync.py show`, last section), when he has set one. Never invent scenes, NPCs, clues or lines. If there is no plan marked ready and none in the conversation, ask for it and stop.

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

- One movement per scene. A planned scene prints whole with `python3 tools/osse/osse.py scene NAME` (or, before it is in the vault, `paths_sync.py board S<n>`): its situation, purpose and Opens on open the movement, its cues become the triggers on the flagged beats, and its exits the ways out. Its Any time cards stay apart from the beats that run in order: show them as ready at any point in the movement. A decision's options show with where each leads or what happens. A floating scene (`~` in the running order) is a movement Tom can call when it fits: leave it unnumbered, at its place in the order, and print its after and before limits. Mark a critical decision plainly. Each names its lead PC, a job for every other PC, the flagged beats, and the pen questions.
- Each movement also carries the stakes (`st`): for each PC who faces a decision in that scene, the decision in one line, then the considerations the game master can offer from that character's history. Use only facts from the plan and the campaign record. Keep sealed secrets out of it. A PC with no decision is left out. This feeds the Stakes view.
- Set `order` on a movement when the plan fixes the order the PCs are taken in.
- Pick the views each movement offers by what the scene is (`TV`). Next in Spotlight moves to the next movement and its first view:

| Scene type | Views |
|---|---|
| Combat | Stat blocks, Health (bars, statuses and resistances for everyone in the fight), Initiative (rolls, damage and healing, bench, add someone), Voices, Roll call |
| Roleplay, investigation | Roll call, Evidence (full width), Voices, Sealed |
| Speeches, endings | Speech view in large type with fill-ins from Roll call, Roll call, Evidence, Sealed |

- Spotlight is always on screen. Stakes opens from Spotlight, each decision with its considerations on a tap. Sealed is a view of its own, closed until tapped.
- Retire views the session does not need. Add a bespoke one when a scene has its own mechanic (S13: The Hand).
- Health and Initiative share one list of combatants (`CMB0`: side, initiative, hit points, AC, attack line, resistances, statuses, in the fight or on the bench). Initiative edits rolls and hit points and moves people to and from the bench; Health shows the result. Keep both, and keep + Add.
- Keep the Export button. Its text must list every beat, clue, roll call state and the fight as plain Markdown, flag what was not reached or not found, and end with the board state so it can be restored. Tom gives it to Claude for the post-session sync, with the summary and transcript.
- Both layouts are tap first: targets 44px or larger, a number pad instead of a text field, nothing that needs hover. Combat pairs the foe tracker with Initiative. The base address picks the layout from the window's shape (portrait gives tall, landscape gives iPad); `#ipad` and `#tall` force it.

## Hand the pen prompts

Each movement has two to four prompts, stored as `[who, prompt, then]`. Write them this way:

- Give half, ask for half. State the part you would have narrated, and leave one gap sized for a single answer. "What happens next?" is too wide.
- Stay inside the character: their memory, feelings, body, senses, choices and past. Never ask a player to invent an NPC's secret, a clue, or the result of their own action. In an investigation, give the clue and ask what the character makes of it.
- Paint the scene for the whole table: name the mood, then ask "what do you see that shows it?" Address these to "Anyone" so nobody is put on the spot.
- Open with what, who, where, when or how. No yes or no questions unless both answers lead somewhere. No questions that need a proper noun.
- Stage it: an easy, concrete question first, then a deeper one in `then`.
- Do not ask what you cannot accept. Fix what the plan needs to stay true.
- Aim at motive and relationships, and plan how the answer comes back later in the scene.

Sources: Jason Cordova's Paint the Scene (The Gauntlet), the Gauntlet forum thread on leading questions, The Alexandrian on description-on-demand, and Sly Flourish on asking the wrong questions.

## 3. Stat blocks

Player characters: carry the blocks forward from the last screen and update them from the current sheets. The **Tonight** call-out lists only what matters this session: defense bonus, the spells, items and features likely to come up, and anything the story hands them.

NPCs: every move must be a published mechanic, or a baseline rule with new flavour. Players should recognize what hit them.

- Start from the closest published block (gladiator, warlord, assassin, a class feature, a spell) and rename. Check the wording against the source, not memory: the Rules and items tab of the vault (`vault/#rules`, the SRD through Open5e) or the 5e.tools data at `https://raw.githubusercontent.com/5etools-mirror-3/5etools-src/main/data/bestiary/bestiary-<source>.json`. Read the 5e.tools data to check; copy only SRD text onto the page.
- End each entry with its source in double braces, for example `{{Command Ally, as the warlord.}}`. The page shows it as a small note.
- Check the math: proficiency bonus fits the challenge rating; attack bonus is ability modifier plus proficiency; save DC is 8 plus modifier plus proficiency; hit points match the hit dice.
- Table rules: normal attack rolls against AC. Do not use player-rolled defense. Show damage in stat-block form, the average with the dice in brackets, for example 14 (1d6 + 4 piercing plus 2d6 poison). Tom rolls damage for named NPCs such as Corvane and Cassian.
- In a PC's **Tonight** call-out, give the AC and the roll the main foe needs to hit it.
- Casters follow their class: only spells on the class or subclass list, no more spells than that level knows, and the right slots. A warlock has few slots, all at the top level, back on a short rest. Scale effects to the slot level used.
- Session rulings go in **Tonight**, written as rulings, with the baseline rule they bend.
- A named NPC with a class is built like a character of that class: every trait is a class feature, subclass feature, invocation, spell or feat a character of that level could have. Do not borrow features from other classes or from unrelated monster blocks. Boss extras (legendary actions) are allowed, and are labelled as that.
- Marquis Corvane is a 12th-level warlock, Fiend patron, Pact of the Blade (2024 rules). His three attacks come from Thirsting Blade and Devouring Blade, and his damage from Hex and Lifedrinker. Keep him that way unless told otherwise.

## 4. Design rules

- One file. The hub's Google Fonts link (Cinzel, Spectral, IBM Plex Mono) is the only outside resource; no other fonts, scripts or images. State lives in `localStorage` under a key unique to the session (`osse-sNN-v1`), so both layouts on one device stay in step. The iPad and the tall screen are separate devices and keep separate state.
- The hub's tokens: `--ink:#0b0908`, `--panel:#16110e`, `--panel-2:#1d1612`, `--gold:#d2a851`, `--gold-hi:#f0d494`, `--gold-lo:#8d6829`, `--velvet:#6b1220`, `--text:#ece2cf`, `--muted:#a99a82`. Cinzel for headings, Spectral for text, Plex Mono for labels and numbers. Panels are the hub's cards; buttons are its gold buttons. Keep the PC colours from the last screen.
- Nothing the game master needs in the moment may sit behind a scroll in Spotlight. The main control of a view sits in its header and never scrolls away. Next names where it goes.
- The top bar ends, at the right, with the DM navigation: `<a class="home" href="../">Table hub</a><a class="home" href="../vault/">Vault</a><a class="home" href="../vault/paths.html">Planner</a>`, styled to the screen.
- Every screen has the game master lock. Put these lines in its `<head>`, exactly (the same as `DM_HEAD` in `tools/osse/pages.py`): `<style>html:not(.dm-ok) body>*:not(#dmlock){display:none!important}</style><script>try{var k=localStorage,g=k.getItem("gus-key-gm");if(!k.getItem("osse-hub-dm")&&g)k.setItem("osse-hub-dm",g);if(k.getItem("osse-hub-dm"))document.documentElement.classList.add("dm-ok")}catch(e){}</script><script src="../assets/dm.js" defer></script>`
- Anything that wipes state needs a second tap. Numbers that change often get a typed field as well as buttons.
- Body text 16px or larger on the iPad, 18px or larger on the tall screen.
- Canadian English. No em dashes.

## 5. Test

Run the `screen` preview server (`.claude/launch.json`) and check in the browser:

1. `#ipad` at 1024 by 740 and `#tall` at 1080 by 1920: every movement and view, nothing cut off in Spotlight, the number pad, no control under 44px.
2. The base address picks the right layout in portrait and in landscape.
3. Click through: Next across all movements, damage entry, roll call taps, evidence ticks, sealed open and close, every stat block and voice.
4. No console errors, and no `{{` left showing.

## 6. Publish

1. Run `python3 tools/osse/pages.py`. It lists the screens in `vault/status.json`, and the hub's game master section then shows the iPad and Tall buttons for the next session and ticks "Draft DM screen". Do not edit `index.html` for a new session.
2. Run the pre-commit check from `CLAUDE.md`. If the build only changed timestamps in `wilds-of-osse.json`, do not commit that file.
3. Commit to main and push.
4. Wait for GitHub Pages, then confirm `https://osse.thomashuet.ca/screen/sNN.html` returns 200 and matches the committed file.
5. Tell Tom the address, what he will see, and anything he must do. Old test state clears with Reset, tapped twice.
