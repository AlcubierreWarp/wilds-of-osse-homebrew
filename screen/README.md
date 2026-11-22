# Table hub

The site's home page, `index.html`, gathers every link: https://osse.thomashuet.ca once its DNS record is in place, https://alcubierrewarp.github.io/wilds-of-osse-homebrew/ until then. Every link opens in a new tab.

- **For the players**: D&D Beyond, Roll20 and Gus's archive. No codes here.
- **Game master**: behind a passcode (Keychain service `osse-dm-passcode`; change it with `relay/gus/deploy.sh --new-dm-passcode`). It keeps players from wandering in; it is not strong security. Inside:
  - Gus's archive: the game master view (opens already unlocked) and Shane's code to hand him. The code comes from the relay (`hub.json`, game master only), so it never sits in this repository. `relay/gus/deploy.sh --new-player-code` changes the code and the hub at once.
  - One folding group per session. Only the newest session starts open; the page remembers what you fold. Put a new session first in the `DM` list.
  - The 5e.tools homebrew raw link, with a Copy button and load steps.

# DM Screen tools: The Toast (Session 12)

Small single-file tools for the 5e.tools DM Screen. Add one with a panel's **Embed** option and paste its address.
They need GitHub Pages turned on for this repository (Settings, Pages, deploy from the `main` branch).

| Tool | Address |
|---|---|
| Round clock | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/clock.html |
| Champions | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/champions.html |
| Knives' turn | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/knives.html |
| Crowd die | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/crowd.html |
| Voices | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/voices.html |
| Initiative | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/initiative.html |
| Stat blocks | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/statblocks.html |
| All seven in one | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/all.html |

The clock, champions, knives and crowd panels share one fight state in the browser and stay in sync.
Voices reads `voices-toast.json` by default; add `?data=<address of another JSON file>` to reuse it for a different scene.
Stat blocks reads `stats-toast.json` by default; add `?stats=<address of another JSON file>` to reuse it. These blocks reflect the Session 12 table rules (player-rolled defense, static damage), not the raw homebrew entries.

## Session 13: The Last Bell

One page, `s13.html`, holds every panel. Everything shares one state in the browser, so a name marked dead or a clue ticked in one panel shows in the others.

Base: https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/s13.html

Whole screen, three tabs laid out for a vertical monitor. Add the tab to the end of the base address:

| Tab | Add | Movements |
|---|---|---|
| Last Bell | `#tab1` | 1 |
| Aftermath | `#tab2` | 2 and 3 |
| Hard Out | `#tab3` | 4 and 5 |

The Next button in Spotlight moves to the right tab by itself. Keys 1, 2 and 3 also switch tabs.

iPad in landscape, tap only: add `#ipad`. Spotlight stays on the left, and the right side shows one view at a time (Fight, Stakes, Stats, Voices, Roll call, Evidence, Speeches, Sealed) with a number pad for damage and initiative. An iPad opening the base address in landscape gets this view by itself. State is kept per device, so the iPad and the Mac do not share it.

Health and Initiative work as a pair. Initiative lists who is in the fight: change a roll in its number box, type hit points and press − or + to damage or heal, and press × to send someone to the bench. Tap a name on the bench to bring them in, or + Add for someone new. Health shows the same people as bars, with statuses and resistances. On the iPad, tapping a number opens a number pad instead of the keyboard.

Export, in the top bar: a text record of the board (beats, evidence found and not found, roll call, the fight, initiative). Copy it, share it or save it as a file, and give it to Claude with the session summary and transcript. Pasting an export back in and tapping Restore puts the board back, on any device.

Single panels, one per 5e.tools Embed. Use these on a landscape screen:

| Panel | Add |
|---|---|
| Spotlight | `#panel=spot` |
| Roll call | `#panel=roll` |
| Health | `#panel=health` |
| Initiative | `#panel=init` |
| Evidence | `#panel=evidence` |
| Voices | `#panel=voices` |
| Speeches | `#panel=speech` |
| Stat blocks | `#panel=stats` |
| Sealed | `#panel=sealed` |
| Stakes | `#panel=stakes` |

## Gus's memory archive

`gus.html` is a terminal for the documents Gus receives. You add files, keep them sealed, and reveal or push them during play. Shane reads them on his own device, and a pushed file opens on his screen within a few seconds.

Address: https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/gus.html

The page itself holds no documents. They live in a private relay on AWS (`relay/gus/`, default profile, ca-central-1), which sends the player only what has been revealed. Game master notes and sealed files never leave the relay.

Two access links open it, one for each role. The keys are in the macOS Keychain, never in this repository:

| Who | Keychain service | Link |
|---|---|---|
| Game master | `osse-gus-gm` | address + `#gm=<key>` |
| Shane | `osse-gus-player` | the plain address, then type the short code (like `ABCD-EFGH`) on the login screen |

A locked terminal shows a login screen; the code is case-insensitive and the dash is optional. A device remembers its code after the first unlock. "Lock this device" at the bottom forgets it. To give Shane a new code, run `relay/gus/deploy.sh --new-player-code`. To replace both keys, run `relay/gus/deploy.sh --new-keys`.

What Gus has opened is kept in the relay, so a new browser or device does not flag old files as new. The game master strip shows when Gus opened a file, with Mark unread and Mark opened to change it.

| Button | What Shane sees |
|---|---|
| Push to Gus's screen | The file opens on his screen with an incoming-file signal |
| Reveal quietly | The file joins his list, marked New |
| Take back | The file leaves his list |

Emergency protocols (files of the Emergency protocol type) sit on their own Emergency tab in the file list. On Gus's screen that tab glows bright red while a protocol he has not opened is waiting; pushing one switches him to it. Everything else is on the Files tab.

Every file is laid out as letter-sized Marshal pages modelled on the handouts: field manual chapters get the chapter block, annexes the file grid, emergency protocols the oxblood band and numbered steps. The Open PDF button at the top opens the attached PDF, or, when there is none, builds a PDF of the pages in the browser and downloads it (html2canvas and jsPDF, loaded on first use; the print dialog is the fallback if they cannot load). The editor's hint lists the markup (`**1.1 Title.**` rules, `## Field exercise`, `## Step 2 · …`, `[stamp: …]`, `---` for the footer, `[page]` for a new page).

New documents written by Claude go in sealed through `relay/gus/add_doc.py` (see the `gus-document` skill): only the game master sees them until revealed or pushed at the table. In the text, `||words||` is blacked out, and the player's copy never holds the words. Attachments can be images or PDFs up to 20 MB.

To test without AWS, start `relay/gus/mock.py` (the `gus-relay-mock` entry in `.claude/launch.json`) and open `http://localhost:8713/gus.html?relay=http://localhost:8714#gm=test-gm`.
