#!/usr/bin/env python3
"""Dafina — design inspiration catalogue — local server (Python standard library only).

Run:   python3 server.py --open        → http://localhost:4610

Everything is driven by the folder tree in  sources/ :

  sources/<Category>/<Sub-category>/<more levels…>/image.png

The app re-reads the tree every couple of seconds, so you can add, move, rename
or delete folders and images in Finder and the catalogue follows. Labels live in
catalogue.json and are matched to images by a content fingerprint, so moving or
renaming a file keeps its labels.

Helper commands for Claude:
  python3 server.py --pending            list images that still need labels (JSON)
  python3 server.py --save entries.json  merge labelled entries (list of objects with "hash")
"""
import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(ROOT, "sources")
TRASH = os.path.join(ROOT, "trash")
CATALOGUE = os.path.join(ROOT, "catalogue.json")
THUMBS = os.path.expanduser("~/Library/Caches/DesignInspirationThumbs")
PORT = int(os.environ.get("PORT", "4610"))
# when this server.py was last changed, as loaded — Start Catalogue.command restarts the server if the file is newer
BUILD = str(int(os.path.getmtime(os.path.abspath(__file__))))
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".heic", ".tif", ".tiff", ".bmp"}
UNSORTED = "Unsorted"

DEFAULT_CATEGORIES = [
    "Web Design", "Logos", "Brochures", "Emails", "Brand Boards", "UI Kits",
    "Digital Paper", "Patterns", "Colour Palettes", "Journals", "Cards", "Images",
    "Paintings", "Mixed Media", "Clipart", "Mockups", "Textures",
]
LABEL_FIELDS = {"title", "style", "summary", "tags", "palette", "typography", "layout", "mood",
                "brief", "recipe", "source", "notes", "favourite", "added", "designMd", "refero"}

LOCK = threading.RLock()
_hash_cache = {}          # abs path -> (mtime_ns, size, hash)
_state_cache = {"v": None, "state": None}


# ---------------------------------------------------------------- catalogue file
def load_catalogue():
    try:
        with open(CATALOGUE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault("entries", [])
    return data


def save_catalogue(data):
    tmp = CATALOGUE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CATALOGUE)


def entries_by_hash(data):
    return {e["hash"]: e for e in data["entries"] if e.get("hash")}


def is_labelled(e):
    return bool(e and e.get("title") and e.get("tags"))


# ---------------------------------------------------------------- folder scanning
def fingerprint(full):
    """Fast content fingerprint: size + first/last 64 KB. Survives moves and renames."""
    st = os.stat(full)
    cached = _hash_cache.get(full)
    if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
        return cached[2]
    h = hashlib.sha1(str(st.st_size).encode())
    with open(full, "rb") as f:
        h.update(f.read(65536))
        if st.st_size > 131072:
            f.seek(-65536, os.SEEK_END)
            h.update(f.read(65536))
    digest = h.hexdigest()[:16]
    _hash_cache[full] = (st.st_mtime_ns, st.st_size, digest)
    return digest


def walk_sources():
    """Yield (rel_dir_parts, dirnames, filenames) skipping hidden things."""
    for dirpath, dirnames, filenames in os.walk(SOURCES):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel = os.path.relpath(dirpath, SOURCES)
        parts = [] if rel == "." else rel.split(os.sep)
        yield dirpath, parts, dirnames, sorted(f for f in filenames if not f.startswith("."))


def tree_version():
    h = hashlib.sha1()
    for dirpath, parts, dirnames, filenames in walk_sources():
        h.update(("/".join(parts) + "|").encode())
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in IMAGE_EXT:
                try:
                    st = os.stat(os.path.join(dirpath, fn))
                except OSError:
                    continue
                h.update(f"{fn}:{st.st_size}:{st.st_mtime_ns};".encode())
    try:
        h.update(str(os.stat(CATALOGUE).st_mtime_ns).encode())
    except OSError:
        pass
    return h.hexdigest()[:12]


def category_order(names, custom=None):
    """The user's dragged order first (catalogue.json "categoryOrder"), then any categories
    not in it yet in the default order, then Unsorted."""
    mine = {c.lower(): i for i, c in enumerate(custom or [])}
    rank = {c.lower(): i for i, c in enumerate(DEFAULT_CATEGORIES)}
    named = [n for n in names if n != UNSORTED]
    named.sort(key=lambda n: (mine.get(n.lower(), len(mine)), rank.get(n.lower(), 999), n.lower()))
    return named + ([UNSORTED] if UNSORTED in names else [])


def build_state():
    with LOCK:
        v = tree_version()
        if _state_cache["v"] == v:
            return _state_cache["state"]
        data = load_catalogue()
        by_hash = entries_by_hash(data)
        cats = {}          # name -> {"count", "subs": {subpath: count}}
        items, dirty = [], False
        for dirpath, parts, dirnames, filenames in walk_sources():
            if parts:
                cat = cats.setdefault(parts[0], {"count": 0, "subs": {}})
                if len(parts) > 1:
                    cat["subs"].setdefault(" / ".join(parts[1:]), 0)
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in IMAGE_EXT:
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    hsh = fingerprint(full)
                except OSError:
                    continue
                category = parts[0] if parts else UNSORTED
                sub = " / ".join(parts[1:]) if len(parts) > 1 else ""
                c = cats.setdefault(category, {"count": 0, "subs": {}})
                c["count"] += 1
                if sub:
                    # count towards each ancestor sub-folder too
                    segs = parts[1:]
                    for i in range(1, len(segs) + 1):
                        key = " / ".join(segs[:i])
                        c["subs"][key] = c["subs"].get(key, 0) + 1
                rel = "/".join(["sources"] + parts + [fn])
                e = by_hash.get(hsh) or {}
                if e and e.get("path") != rel:
                    e["path"] = rel
                    dirty = True
                item = {k: v2 for k, v2 in e.items() if k != "designMd"}
                item.update({
                    "hash": hsh, "path": rel, "file": fn, "category": category, "sub": sub,
                    "labelled": is_labelled(e), "hasDesignMd": bool(e.get("designMd")),
                    "mtime": int(os.path.getmtime(full)),
                })
                if not item.get("added"):
                    item["added"] = time.strftime("%Y-%m-%d", time.localtime(item["mtime"]))
                items.append(item)
        if dirty:
            save_catalogue(data)
            v = tree_version()
        state = {
            "v": v,
            "categories": [
                {"name": n, "count": cats[n]["count"],
                 "subs": [{"path": p, "count": cnt} for p, cnt in sorted(cats[n]["subs"].items(), key=lambda x: x[0].lower())]}
                for n in category_order(set(cats), data.get("categoryOrder"))
            ],
            "items": items,
        }
        _state_cache.update(v=v, state=state)
        return state


# ---------------------------------------------------------------- file helpers
def safe_segment(s, fallback="untitled"):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", (s or "").strip()).strip(" .-")
    return s[:80] or fallback


def folder_for(category, sub):
    """Folder for a category + sub-path, reusing existing folders whatever their capitalisation."""
    parts = [safe_segment(category, "Unsorted")] + [safe_segment(p) for p in re.split(r"\s*/\s*", sub or "") if p.strip()]
    if parts[0] == UNSORTED and len(parts) == 1:
        return SOURCES
    cur = SOURCES
    for p in parts:
        try:
            match = next((d for d in os.listdir(cur) if d.lower() == p.lower() and os.path.isdir(os.path.join(cur, d))), None)
        except FileNotFoundError:
            match = None
        cur = os.path.join(cur, match or p)
    return cur


def unique_path(folder, base, ext):
    os.makedirs(folder, exist_ok=True)
    cand, i = os.path.join(folder, base + ext), 2
    while os.path.exists(cand):
        cand, i = os.path.join(folder, f"{base}-{i}{ext}"), i + 1
    return cand


def resolve_source_path(rel):
    full = os.path.abspath(os.path.join(ROOT, rel or ""))
    return full if full.startswith(SOURCES + os.sep) and os.path.isfile(full) else None


def upsert_entry(hsh, rel, changes):
    data = load_catalogue()
    by_hash = entries_by_hash(data)
    e = by_hash.get(hsh)
    if not e:
        e = {"hash": hsh, "path": rel, "added": time.strftime("%Y-%m-%d")}
        data["entries"].append(e)
    for k, v in changes.items():
        if k in LABEL_FIELDS:
            e[k] = v
    if rel:
        e["path"] = rel
    save_catalogue(data)
    return e


def save_image(folder, filename, blob, meta):
    base, ext = os.path.splitext(os.path.basename(filename or "screenshot.png"))
    ext = ext.lower() if ext.lower() in IMAGE_EXT else ".png"
    full = unique_path(folder, safe_segment(base, "screenshot"), ext)
    with open(full, "wb") as f:
        f.write(blob)
    rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
    meta = {k: v for k, v in meta.items() if v}
    hsh = fingerprint(full)
    if meta:
        upsert_entry(hsh, rel, meta)
    return rel, hsh


# ---------------------------------------------------------------- Refero import
def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DesignInspirationCatalogue)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return body if binary else body.decode("utf-8", "replace")


def meta_tag(page, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), page)
    return html.unescape(m.group(1)) if m else ""


def import_refero(url, category, sub):
    u = urlparse(url.strip())
    if u.scheme != "https" or u.netloc != "styles.refero.design" or not u.path.startswith("/style/"):
        raise ValueError("not a styles.refero.design/style/… link")
    page = fetch(url.strip())
    title = re.sub(r"\s*(design system)?\s*\|\s*Refero Styles\s*$", "", meta_tag(page, "og:title"), flags=re.I).strip() or "Refero style"
    img_url = meta_tag(page, "og:image")
    if not img_url.startswith("https://"):
        raise ValueError("no preview image found on that page")
    design_md = ""
    for block in re.findall(r"<code[^>]*>(.*?)</code>", page, re.S):
        if "Style Reference" in block[:300]:
            design_md = html.unescape(re.sub(r"<[^>]+>", "", block)).strip()
            break
    blob = fetch(img_url, binary=True)
    ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
    rel, hsh = save_image(folder_for(category, sub), title + ext, blob, {
        "source": url.strip(),
        "notes": meta_tag(page, "og:description"),
        "designMd": design_md,
        "refero": {"category": meta_tag(page, "category"), "title": title},
    })
    return {"title": title, "path": rel, "hash": hsh, "designMd": bool(design_md)}


# ---------------------------------------------------------------- website screenshots
BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser():
    return next((b for b in BROWSERS if os.path.exists(b)), None)


def page_info(url):
    """Title and description of a web page (best effort: some sites block simple requests)."""
    try:
        page = fetch(url)
    except Exception:
        return "", "", ""
    title = meta_tag(page, "og:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    desc = meta_tag(page, "og:description") or meta_tag(page, "description")
    return title, desc, meta_tag(page, "og:image")


def capture_website(url, tall=False):
    """Screenshot a web page with the Mac's own Chrome (or Edge/Brave), in the background. Returns (png bytes, title, description)."""
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("not a web link")
    title, desc, og_image = page_info(url.strip())
    browser = find_browser()
    if browser:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "shot.png")
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                            "--no-default-browser-check", f"--user-data-dir={os.path.join(tmp, 'profile')}",
                            "--window-size=1440,%d" % (3000 if tall else 1000), "--virtual-time-budget=12000",
                            f"--screenshot={out}", url.strip()], capture_output=True, timeout=90)
            if os.path.exists(out) and os.path.getsize(out) > 2000:
                with open(out, "rb") as f:
                    return f.read(), title, desc
    if og_image.startswith(("https://", "http://")):
        # no browser to take a screenshot with: fall back to the page's own preview image
        return fetch(og_image, binary=True), title, desc
    raise ValueError("couldn't take a screenshot (install Google Chrome, or the page may block it)")


# ---------------------------------------------------------------- thumbnails
def thumbnail(full, hsh, size):
    os.makedirs(THUMBS, exist_ok=True)
    out = os.path.join(THUMBS, f"{hsh}-{size}.jpg")
    if os.path.exists(out):
        return out
    try:
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", "-Z", str(size), full, "--out", out],
                       check=True, capture_output=True, timeout=60)
        return out
    except Exception:
        return None


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        if "/api/" in (self.path or "") and "/api/version" not in self.path:
            sys.stderr.write("%s\n" % (fmt % args))

    # The Figma plugin runs in a sandboxed window whose origin is "null". It may only list
    # categories and add images, never edit, move or delete.
    FIGMA_PATHS = ("/api/categories", "/api/upload")

    def from_figma(self):
        return self.headers.get("Origin") == "null" and urlparse(self.path).path in self.FIGMA_PATHS

    def end_headers(self):
        if self.from_figma():
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")   # Chrome/Figma ask this before a page may talk to this computer
        if not getattr(self, "_cacheable", False):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, full, ctype):
        with open(full, "rb") as f:
            body = f.read()
        self._cacheable = True
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/version":
            with LOCK:
                return self.send_json({"v": tree_version()})
        if u.path == "/api/build":
            return self.send_json({"build": BUILD})
        if u.path == "/api/categories":
            st = build_state()
            return self.send_json({"categories": [{"name": c["name"], "subs": [x["path"] for x in c["subs"]]} for c in st["categories"]]})
        if u.path == "/api/state":
            return self.send_json(build_state())
        if u.path == "/api/designmd":
            hsh = parse_qs(u.query).get("hash", [""])[0]
            e = entries_by_hash(load_catalogue()).get(hsh) or {}
            return self.send_json({"designMd": e.get("designMd", "")})
        if u.path == "/thumb":
            q = parse_qs(u.query)
            full = resolve_source_path(q.get("p", [""])[0])
            size = 2400 if q.get("s", [""])[0] == "l" else 900
            if not full:
                return self.send_error(404)
            if os.path.splitext(full)[1].lower() in {".svg", ".gif"}:
                return self.send_file(full, "image/svg+xml" if full.endswith(".svg") else "image/gif")
            out = thumbnail(full, fingerprint(full), size)
            return self.send_file(out, "image/jpeg") if out else self.send_file(full, self.guess_type(full))
        if any(part.startswith(".") for part in u.path.split("/") if part) or u.path.endswith(".py"):
            return self.send_error(404)
        return super().do_GET()

    def allowed_origin(self):
        """Only this app's own page and the Dafina Chrome extension may change things; other websites may not."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        if origin == "null":
            return self.from_figma()
        return origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}") or origin.startswith("chrome-extension://")

    def do_OPTIONS(self):
        # browsers ask first before the Figma plugin may send JSON
        if self.from_figma():
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_error(403)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.allowed_origin() or "json" not in (self.headers.get("Content-Type") or ""):
            return self.send_json({"error": "not allowed"}, 403)
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except Exception:
            return self.send_json({"error": "bad request"}, 400)
        try:
            if path in ("/api/website", "/api/imageurl"):
                return self.send_json(self.fetch_and_save(path, data))
            with LOCK:
                result = self.route(path, data)
                _state_cache["v"] = None
            return self.send_json(result)
        except LookupError as err:
            return self.send_json({"error": str(err)}, 404)
        except Exception as err:
            return self.send_json({"error": str(err)}, 400)

    def fetch_and_save(self, path, data):
        """Website screenshots and images from a link: download first (slow), then save under the lock."""
        url = (data.get("url") or "").strip()
        if path == "/api/website":
            if urlparse(url).netloc == "styles.refero.design":
                with LOCK:
                    r = import_refero(url, data.get("category") or "Web Design", data.get("sub", "Refero"))
                    _state_cache["v"] = None
                return {"ok": True, "title": r["title"], "path": r["path"], "hash": r["hash"], "refero": True}
            blob, title, desc = capture_website(url, bool(data.get("tall")))
            name = title or urlparse(url).netloc.replace("www.", "")
            ext = ".png" if blob[:4] == b"\x89PNG" else ".jpg"
            meta = {"source": url, "notes": "\n".join(x for x in (data.get("notes") or "", desc) if x)}
        else:  # /api/imageurl: an image on a page, from the extension's right-click menu
            blob = fetch(url, binary=True)
            if len(blob) < 200:
                raise ValueError("that image couldn't be downloaded")
            name = data.get("title") or os.path.basename(urlparse(url).path) or "image"
            name = os.path.splitext(name)[0]
            ext = os.path.splitext(urlparse(url).path)[1].lower()
            ext = ext if ext in IMAGE_EXT else (".png" if blob[:4] == b"\x89PNG" else ".jpg")
            meta = {"source": (data.get("page") or url).strip(), "notes": data.get("notes") or ""}
        with LOCK:
            rel, hsh = save_image(folder_for(data.get("category"), data.get("sub")), name + ext, blob, meta)
            _state_cache["v"] = None
        return {"ok": True, "title": name, "path": rel, "hash": hsh}

    def route(self, path, data):
        if path == "/api/upload":
            raw = data.get("data", "")
            blob = base64.b64decode(raw.split(",", 1)[1] if "," in raw else raw)
            rel, hsh = save_image(folder_for(data.get("category"), data.get("sub")), data.get("filename"), blob,
                                  {"source": (data.get("source") or "").strip(), "notes": (data.get("notes") or "").strip()})
            return {"ok": True, "path": rel, "hash": hsh}

        if path == "/api/refero":
            done, failed = [], []
            for url in [u for u in data.get("urls", []) if u.strip()]:
                try:
                    done.append(import_refero(url, data.get("category") or "Web Design", data.get("sub", "Refero")))
                except Exception as err:
                    failed.append({"url": url, "error": str(err)})
            return {"ok": True, "done": done, "failed": failed}

        if path == "/api/entry":
            full = resolve_source_path(data.get("path"))
            if not full:
                raise LookupError("image not found")
            rel = data["path"]
            changes = data.get("changes") or {}
            if "category" in changes or "sub" in changes:
                dest_folder = folder_for(changes.get("category"), changes.get("sub"))
                if os.path.abspath(dest_folder) != os.path.dirname(full):
                    base, ext = os.path.splitext(os.path.basename(full))
                    dest = unique_path(dest_folder, base, ext)
                    shutil.move(full, dest)
                    rel = os.path.relpath(dest, ROOT).replace(os.sep, "/")
            e = upsert_entry(data["hash"], rel, changes)
            return {"ok": True, "path": rel, "entry": {k: v for k, v in e.items() if k != "designMd"}}

        if path == "/api/delete":
            full = resolve_source_path(data.get("path"))
            if full:
                os.makedirs(TRASH, exist_ok=True)
                shutil.move(full, os.path.join(TRASH, f"{int(time.time())}-{os.path.basename(full)}"))
            # keep the labels if an identical copy of the image is still in sources/
            h = data.get("hash")
            still_there = any(os.path.splitext(f)[1].lower() in IMAGE_EXT and fingerprint(os.path.join(d, f)) == h
                              for d, _, _, files in walk_sources() for f in files)
            if not still_there:
                cat = load_catalogue()
                cat["entries"] = [e for e in cat["entries"] if e.get("hash") != h]
                save_catalogue(cat)
            return {"ok": True}

        if path == "/api/openclaude":
            # the "Label with Claude" button: bring the Claude desktop app to the front (macOS)
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Claude"])
                return {"ok": True}
            return {"ok": False}

        if path == "/api/folder":
            os.makedirs(folder_for(data.get("category"), data.get("sub")), exist_ok=True)
            return {"ok": True}

        if path == "/api/order":
            # the category pill order the user dragged into place; an empty list resets to the default
            order = [str(n).strip() for n in (data.get("order") or []) if str(n).strip()]
            with LOCK:
                cat = load_catalogue()
                if order:
                    cat["categoryOrder"] = order
                else:
                    cat.pop("categoryOrder", None)
                save_catalogue(cat)
            return {"ok": True}

        if path == "/api/renamefolder":
            # rename a category (top-level folder) or a sub-folder; labels follow because they're matched by image content
            cat_name, sub = (data.get("category") or "").strip(), (data.get("sub") or "").strip()
            new = safe_segment(data.get("name") or "", "").lower()
            if not cat_name or cat_name == UNSORTED or not new:
                raise ValueError("choose a folder and type a new name")
            src = folder_for(cat_name, sub)
            if not os.path.isdir(src) or os.path.abspath(src) in (SOURCES, os.path.abspath(TRASH)):
                raise LookupError("that folder wasn't found")
            dest = os.path.join(os.path.dirname(src), new)
            if os.path.basename(src) == new:
                return {"ok": True, "category": cat_name, "sub": sub}
            clash = next((d for d in os.listdir(os.path.dirname(src)) if d.lower() == new and os.path.join(os.path.dirname(src), d) != src), None)
            if clash:
                raise ValueError(f"there's already a folder called “{clash}” there")
            if os.path.basename(src).lower() == new:      # only the capitalisation changes: go via a temporary name
                tmp = src + ".renaming"
                os.rename(src, tmp)
                os.rename(tmp, dest)
            else:
                os.rename(src, dest)
            if sub:
                parts = [p for p in re.split(r"\s*/\s*", sub) if p.strip()]
                new_sub = " / ".join(parts[:-1] + [new])
                return {"ok": True, "category": cat_name, "sub": new_sub}
            cat = load_catalogue()
            if cat.get("categoryOrder"):
                cat["categoryOrder"] = [new if n == cat_name else n for n in cat["categoryOrder"]]
                save_catalogue(cat)
            return {"ok": True, "category": new, "sub": ""}

        raise LookupError("unknown endpoint")


# ---------------------------------------------------------------- CLI helpers
def cli_pending():
    state = build_state()
    by_hash = entries_by_hash(load_catalogue())
    out = []
    for it in state["items"]:
        if it["labelled"]:
            continue
        e = by_hash.get(it["hash"], {})
        out.append({"hash": it["hash"], "path": it["path"], "category": it["category"], "sub": it["sub"],
                    "source": e.get("source", ""), "notes": e.get("notes", ""),
                    "refero": e.get("refero"), "hasDesignMd": bool(e.get("designMd"))})
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cli_save(path):
    with open(path, encoding="utf-8") as f:
        incoming = json.load(f)
    if isinstance(incoming, dict):
        incoming = incoming.get("entries", [incoming])
    with LOCK:
        data = load_catalogue()
        by_hash = entries_by_hash(data)
        for new in incoming:
            hsh = new.get("hash")
            if not hsh:
                continue
            e = by_hash.get(hsh)
            if not e:
                e = {"hash": hsh}
                data["entries"].append(e)
                by_hash[hsh] = e
            for k, v in new.items():
                if k in LABEL_FIELDS or k == "path":
                    e[k] = v
            e.setdefault("added", time.strftime("%Y-%m-%d"))
        save_catalogue(data)
    print(f"saved {len(incoming)} entr{'y' if len(incoming) == 1 else 'ies'}")


def ensure_folders():
    if not os.path.isdir(SOURCES):
        for c in DEFAULT_CATEGORIES:
            os.makedirs(os.path.join(SOURCES, c), exist_ok=True)
    if not os.path.exists(CATALOGUE):
        save_catalogue({"entries": []})


def main():
    ensure_folders()
    if "--pending" in sys.argv:
        return cli_pending()
    if "--save" in sys.argv:
        return cli_save(sys.argv[sys.argv.index("--save") + 1])
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Dafina catalogue running at {url}  (Ctrl+C to stop)")
    threading.Thread(target=build_state, daemon=True).start()
    if "--open" in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
