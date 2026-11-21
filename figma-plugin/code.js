// Save to Dafina — exports the selected frames as PNGs and hands them to the plugin window,
// which sends them to the Dafina app running on this computer.
figma.showUI(__html__, { width: 340, height: 520, themeColors: true });

const MAX_SIDE = 4096; // keep exports to a sensible size

function selectionInfo() {
  const items = figma.currentPage.selection
    .filter(n => "exportAsync" in n && n.width > 0 && n.height > 0)
    .map(n => ({ id: n.id, name: n.name, w: Math.round(n.width), h: Math.round(n.height), type: n.type }));
  figma.ui.postMessage({ type: "selection", items, file: figma.root.name, page: figma.currentPage.name });
}

function linkTo(node) {
  // figma.fileKey is only available in some plugin set-ups; without it we skip the link
  return figma.fileKey ? `https://www.figma.com/design/${figma.fileKey}/?node-id=${encodeURIComponent(node.id.replace(":", "-"))}` : "";
}

figma.on("selectionchange", selectionInfo);
figma.on("currentpagechange", selectionInfo);

figma.ui.onmessage = async msg => {
  if (msg.type === "ready") {
    const saved = (await figma.clientStorage.getAsync("dafina")) || {};
    figma.ui.postMessage({ type: "saved", saved });
    selectionInfo();
  }
  if (msg.type === "remember") await figma.clientStorage.setAsync("dafina", msg.value);
  if (msg.type === "export") {
    for (const id of msg.ids) {
      const node = await figma.getNodeByIdAsync(id);
      if (!node || !("exportAsync" in node)) continue;
      const scale = Math.max(0.1, Math.min(msg.scale || 2, MAX_SIDE / Math.max(node.width, node.height)));
      try {
        const bytes = await node.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: scale } });
        figma.ui.postMessage({ type: "image", id, name: node.name, bytes, link: linkTo(node), where: `${figma.root.name} › ${figma.currentPage.name} › ${node.name}` });
      } catch (err) {
        figma.ui.postMessage({ type: "failed", id, name: node.name, error: String(err && err.message || err) });
      }
    }
    figma.ui.postMessage({ type: "exported" });
  }
  if (msg.type === "notify") figma.notify(msg.text);
  if (msg.type === "close") figma.closePlugin();
};
