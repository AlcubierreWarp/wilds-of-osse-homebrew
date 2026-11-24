/* The game master lock, on every DM page. One unlock opens every DM page, the hub and Gus's archive in this browser
   (they share the key "osse-hub-dm"); locking any of them locks them all. It keeps players from wandering in; it is not strong security.
   The page's head hides everything until html.dm-ok is set (DM_HEAD in tools/osse/pages.py; the session-screen skill has the same lines). */
(() => {
const KEY = "osse-hub-dm", GUS = "gus-key-gm", root = document.documentElement;
const RELAY = (location.hostname === "localhost" && new URLSearchParams(location.search).get("relay"))
  || "https://2srnsytz3rqi3jke23bz643jhq0irvei.lambda-url.ca-central-1.on.aws";
const get = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
const set = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
const del = k => { try { localStorage.removeItem(k); } catch (e) {} };
const norm = v => { const t = String(v || "").trim(), c = t.replace(/[^A-Za-z0-9]/g, "").toUpperCase(); return c.length === 8 && t.length <= 11 ? c.slice(0, 4) + "-" + c.slice(4) : t; };
async function check(code) {   // true, false (refused), or null when the relay gave no answer
  try { const r = await fetch(RELAY + "/gm", {headers: {"x-gus-key": code}, cache: "no-store"}); return r.ok ? true : r.status === 401 || r.status === 403 ? false : null; }
  catch (e) { return null; }
}
function lock(say) {
  root.classList.remove("dm-ok");
  if (document.getElementById("dmlock")) return;
  const hub = location.pathname.replace(/(vault|screen)\/[^/]*$/, "");
  document.body.insertAdjacentHTML("beforeend", `<style>
#dmlock{position:fixed;inset:0;z-index:9999;overflow:auto;display:grid;grid-template-columns:minmax(0,1fr);place-items:center;padding:20px;background:radial-gradient(ellipse 80% 50% at 50% 0%,rgba(30,44,74,.35),transparent 70%),#0a0d14;color:#ddd3c0;font:17px/1.55 "Spectral",Georgia,serif}
#dmlock,#dmlock *{box-sizing:border-box}#dmlock form{display:flex;flex-direction:column;align-items:center;gap:12px;width:min(420px,100%);padding:28px 22px;text-align:center;border:1px solid rgba(201,170,110,.32);border-radius:6px;background:#121722}
#dmlock i{display:grid;place-items:center;width:54px;height:54px;border-radius:50%;font:600 22px/1 Georgia,serif;color:#e6cc8f;background:radial-gradient(circle at 40% 35%,#8e1d2e,#6b1220 60%,#3a0a12);box-shadow:0 0 0 2px #7c6033}
#dmlock h1{margin:0;font:600 22px/1.2 "Cinzel",Georgia,serif;letter-spacing:.05em;color:#e6cc8f;text-shadow:none}#dmlock p{margin:0;color:#a9a397}
#dmlock div{display:flex;gap:8px;width:100%}
#dmlock input{flex:1;min-width:0;padding:11px 12px;text-align:center;font:500 18px/1.2 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.16em;text-transform:uppercase;color:#e6cc8f;background:#0a0d14;border:1px solid #7c6033;border-radius:4px}
#dmlock button{padding:0 18px;min-height:46px;border:1px solid #e6cc8f;border-radius:4px;cursor:pointer;font:600 13px/1 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:#1c1206;background:#c9a45a}
#dmlock .bad{min-height:1.5em;color:#ff9a9f;font-size:15px}#dmlock a{color:#a9a397;font-size:15px}
#dmlock :focus-visible{outline:2px solid #86b8e6;outline-offset:2px}</style>
<form novalidate autocomplete="off"><i aria-hidden="true">✦</i><h1>Game master only</h1><p>One unlock opens every game master page in this browser.</p>
<div><input placeholder="Passcode" aria-label="Passcode" autocapitalize="characters" autocorrect="off" spellcheck="false" maxlength="80"><button>Enter</button></div>
<p class="bad" role="alert"></p><a href="${hub}">Back to the table hub</a></form>`.replace("<form", '<div id="dmlock" style="display:none"></div><form'));
  const f = document.body.lastElementChild, box = document.getElementById("dmlock"); box.append(f); box.style.display = "";
  const inp = f.querySelector("input"), msg = f.querySelector(".bad"); msg.textContent = say || "";
  f.addEventListener("keydown", e => e.stopPropagation());   // the page's own shortcuts stay out of the passcode box (the DM screen swallows Enter)
  f.addEventListener("submit", async e => {
    e.preventDefault(); const code = norm(inp.value); if (!code) { msg.textContent = "Enter the passcode."; return; }
    msg.textContent = "Checking"; const ok = await check(code);
    if (ok === null) { msg.textContent = "The relay can't be reached. Check the connection."; return; }
    if (!ok) { msg.textContent = "That passcode was not accepted."; inp.select(); return; }
    set(KEY, code); set(GUS, code); location.reload();   // the page starts again with the passcode in hand
  });
  inp.focus();
}
addEventListener("storage", e => {   // locked or unlocked in another tab
  if (e.key !== KEY && e.key !== null) return;
  if (!get(KEY)) lock(); else if (!root.classList.contains("dm-ok")) location.reload();
});
addEventListener("pageshow", e => { if (e.persisted && !get(KEY)) lock(); });   // back button
const code = get(KEY);
if (!code) { lock(); return; }
let seen = null; try { seen = sessionStorage.getItem("osse-dm-ok"); } catch (e) {}
if (seen !== code) check(code).then(ok => {   // once per tab: is the saved passcode still good? No answer leaves the page open, so a dropped connection never locks the table out
  if (ok) { try { sessionStorage.setItem("osse-dm-ok", code); } catch (e) {} }
  if (ok === false) { del(KEY); del(GUS); lock("The passcode saved in this browser no longer works."); }
});
})();
