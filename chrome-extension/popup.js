// Save to Dafina: sends the current page (screenshot + link) to the Dafina app running on this Mac.
const APP = "http://localhost:4610";
const $ = id => document.getElementById(id);
const UPPER = ["ui", "ux", "uk", "us", "3d", "ai"];
const nice = s => (s || "").split(" ").map(w => UPPER.includes(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
let tab = null, cats = [];

async function api(path, body) {
  const r = await fetch(APP + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `error ${r.status}`);
  return j;
}
function say(text, kind) { const m = $("msg"); m.hidden = false; m.className = "msg " + kind; m.innerHTML = text; }
function fillSubs() {
  const c = cats.find(x => x.name === $("cat").value);
  $("subs").innerHTML = (c ? c.subs : []).map(s => `<option value="${s.path.replace(/"/g, "&quot;")}">`).join("");
}
function busy(on) { $("saveView").disabled = $("saveLong").disabled = on; }
function choice() { return { category: $("cat").value, sub: $("sub").value.trim(), notes: $("note").value.trim() }; }
function remember() { chrome.storage.local.set({ cat: $("cat").value, sub: $("sub").value.trim() }); }
function done(r) {
  const where = r.path.replace(/^sources\//, "").split("/").slice(0, -1).map(nice).join(" › ");
  say(`✓ Saved to <b>${where || "your library"}</b>. Ask Claude to “label my dafina” when you're ready.`, "ok");
}
const fileName = () => ($("title").value.trim() || new URL(tab.url).hostname).replace(/[\\/:*?"<>|]+/g, "-").slice(0, 80) + ".png";

async function init() {
  [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  $("title").value = tab.title || "";
  $("url").textContent = tab.url;
  try {
    const st = await api("/api/state");
    cats = st.categories.filter(c => c.name !== "Unsorted");
    const saved = await chrome.storage.local.get(["cat", "sub"]);
    $("cat").innerHTML = cats.map(c => `<option value="${c.name.replace(/"/g, "&quot;")}">${nice(c.name)}</option>`).join("");
    $("cat").value = cats.some(c => c.name === saved.cat) ? saved.cat : (cats.find(c => /web design/i.test(c.name)) || cats[0] || {}).name || "";
    $("sub").value = saved.cat === $("cat").value ? (saved.sub || "") : "";
    fillSubs();
  } catch {
    $("offline").hidden = false; $("form").hidden = true; return;
  }
  if (!/^https?:/.test(tab.url)) { busy(true); say("This page can't be saved. Open a website first.", "info"); }
}
$("cat").onchange = () => { $("sub").value = ""; fillSubs(); };

$("saveView").onclick = async () => {
  busy(true); say("Saving…", "info");
  try {
    const data = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    const r = await api("/api/upload", { ...choice(), filename: fileName(), data, source: tab.url });
    remember(); done(r);
  } catch (err) { say("Couldn't save: " + err.message, "bad"); }
  busy(false);
};
$("saveLong").onclick = async () => {
  busy(true); say("Taking a longer capture… this can take up to 20 seconds.", "info");
  try {
    const r = await api("/api/website", { ...choice(), url: tab.url, tall: true });
    remember(); done(r);
  } catch (err) {
    say(/not found|404/i.test(err.message) ? "Restart Dafina (double-click Start Catalogue) to turn this on." : "Couldn't save: " + err.message, "bad");
  }
  busy(false);
};
init();
