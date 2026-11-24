# Table hub

The site's home page, `index.html`, gathers every link: https://osse.thomashuet.ca once its DNS record is in place, https://alcubierrewarp.github.io/wilds-of-osse-homebrew/ until then. Links open in the same tab; Command-click opens one in a new tab.

- **Theme**: the footer switches between Original and Cover poster (the campaign cover, `assets/poster.webp`, full width behind the page, which rises over its lower third and sinks it into the dark as it scrolls). Each browser remembers its choice.
- **For the players**: D&D Beyond, Roll20, Discord, the chronicle, the codex (what the party knows, with a rules lookup) and Gus's archive. No codes here.
- **Game master**: behind a passcode (Keychain service `osse-dm-passcode`; change it with `relay/gus/deploy.sh --new-dm-passcode`, or pipe a chosen one into `--set-dm-passcode`). It keeps players from wandering in; it is not strong security. One unlock opens the hub's section, every DM page (`assets/dm.js`) and Gus's archive in that browser; Lock this browser closes them all. Inside:
  - Gus's archive code, to hand to Shane. While the section is unlocked, the players' archive button opens the game master view. The code comes from the relay (`hub.json`, game master only), so it never sits in this repository. `relay/gus/deploy.sh --new-player-code` changes the code and the hub at once.
  - Links: the next session's screen (iPad and Tall) and past screens, the Ossë vault and the Session planner. Nothing from the players' section is repeated.
  - A checklist for the next session in phases. Two items tick themselves from `vault/status.json` and `chronicle/chronicle.json` (previous session synced, DM screen drafted); the rest are ticked by hand and kept in the browser per session.
  - The homebrew file's link, small, at the bottom.
  - The session number, the screens and the ticks come from `vault/status.json`, which `tools/osse/build.py` rewrites. Nothing in `index.html` changes from one session to the next; its links are `GM_LINKS` and its checklist `CHECKLIST` and `PHASES`.

# Session screens

One page per session, `sNN.html`, with an iPad layout (`#ipad`) and a tall layout for the vertical 1080p monitor (`#tall`). The `session-screen` skill builds them. The hub's game master section links the next session's screen and lists the older ones.

`s13.html` is the last screen built the old way (three tabs for a 5e.tools Embed, `#tab1` to `#tab3`, single panels at `#panel=<name>`, and `#ipad`).

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
| Push to Gus's screen | A full-screen alert names the file, then clears. The file waits in his list marked New (a pushed emergency protocol also flashes his Emergency tab). He opens it himself. Pushing a file he has already read marks it New again. |
| Reveal quietly | The file joins his list, marked New. No alert, no flashing tab. |
| Take back | The file leaves his list |

Emergency protocols (files of the Emergency protocol type) sit on their own Emergency tab in the file list. On Gus's screen that tab is filled bright red and pulses while a pushed protocol he has not opened is waiting, and goes back to a red outline once he opens it. Nothing on his screen opens by itself. Everything else is on the Files tab.

Every file is laid out as letter-sized Marshal pages modelled on the handouts: field manual chapters get the chapter block, annexes the file grid, emergency protocols the oxblood band and numbered steps. The Open PDF button at the top opens the attached PDF, or, when there is none, builds a PDF of the pages in the browser and downloads it (html2canvas and jsPDF, loaded on first use; the print dialog is the fallback if they cannot load). The editor's hint lists the markup (`**1.1 Title.**` rules, `## Field exercise`, `## Step 2 · …`, `[stamp: …]`, `---` for the footer, `[page]` for a new page).

New documents written by Claude go in sealed through `relay/gus/add_doc.py` (see the `gus-document` skill): only the game master sees them until revealed or pushed at the table. In the text, `||words||` is blacked out, and the player's copy never holds the words. Attachments can be images or PDFs up to 20 MB.

To test without AWS, start `relay/gus/mock.py` (the `gus-relay-mock` entry in `.claude/launch.json`) and open `http://localhost:8713/gus.html?relay=http://localhost:8714#gm=test-gm`.
