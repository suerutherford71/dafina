// Right-click menu: save one image, or the visible page, straight to Dafina using the last category you chose.
const APP = "http://localhost:4610";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "dafina-image", title: "Save image to Dafina", contexts: ["image"] });
  chrome.contextMenus.create({ id: "dafina-page", title: "Save this page to Dafina", contexts: ["page"] });
});

async function post(path, body) {
  const r = await fetch(APP + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `error ${r.status}`);
  return j;
}
function badge(text, colour) {
  chrome.action.setBadgeBackgroundColor({ color: colour });
  chrome.action.setBadgeText({ text });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 4000);
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const { cat = "", sub = "" } = await chrome.storage.local.get(["cat", "sub"]);
  try {
    if (info.menuItemId === "dafina-image") {
      await post("/api/imageurl", { url: info.srcUrl, page: info.pageUrl, category: cat, sub, title: (tab && tab.title) || "" });
    } else {
      const data = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
      const name = ((tab.title || new URL(tab.url).hostname).replace(/[\\/:*?"<>|]+/g, "-").slice(0, 80)) + ".png";
      await post("/api/upload", { category: cat, sub, filename: name, data, source: tab.url });
    }
    badge("✓", "#1cc691");
  } catch (err) {
    badge("!", "#ff6b4a");
    console.warn("Dafina:", err.message);
  }
});
