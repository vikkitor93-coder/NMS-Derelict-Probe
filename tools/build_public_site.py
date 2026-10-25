"""Build the public static site into the atlas clone (GitHub Pages serves the repo root).

  python -I tools/build_public_site.py ATLAS_DIR [--gate on|off] [--check]
  NMS_SITE_PASSWORD=... python -I tools/build_public_site.py --set-password       (writes tools/public_site_gate.json)

Copies an explicit WHITELIST of files from viewer/static/ into ATLAS_DIR, writes config.js (staticSite true, siteBase from
viewer/static/config.js, the gate), robots.txt, .nojekyll and the index.html with Open Graph tags. Nothing else is
copied, and the build refuses to run if any copied path is under a game-derived folder (glyphs/ official icons, models/
game meshes and texture atlas, compact/ experiment data) or is a PNG/image/mesh file. The cards (s/, preview.png) come from
tools/build_share_cards.py; run that too.

Gate: a soft password check in the browser (viewer/static/gate.js). The password is never stored: tools/public_site_gate.json
holds only a random salt and SHA-256(salt + ":" + password). Gate off = `--gate off` or "enabled": false in that file, or
edit gate.enabled in the published config.js. Deterministic: same inputs, same bytes; unchanged files are not rewritten.
Returns/prints the changed repo paths; does not run git (commit under atlas.repo_lock).
"""
import hashlib
import json
import os
import re
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_share_cards as cards  # noqa: E402

STATIC = HERE.parent / "viewer" / "static"
GATE_FILE = HERE / "public_site_gate.json"
FILES = ["index.html", "app.js", "app.css", "model.js", "view3d.js", "compact.js", "credits.js", "share.js", "gate.js",
         "piece_props.json"]
SUBTREES = {"glyphs-svg": r"^[0-9a-f]\.svg$", "vendor/three": r"^(three\.module\.min\.js|OrbitControls\.js|LICENSE)$"}
FORBIDDEN_PARTS = {"glyphs", "models", "compact", "meshcache", "pieces"}
FORBIDDEN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".glb", ".gltf", ".dds", ".bin", ".mbin", ".obj", ".fbx"}


def plan():
    out = {}
    for f in FILES:
        out[f] = STATIC / f
    for sub, pat in SUBTREES.items():
        for p in sorted((STATIC / sub).iterdir()):
            if re.match(pat, p.name):
                out[f"{sub}/{p.name}"] = p
    for rel in out:
        parts = set(Path(rel).parts)
        if parts & FORBIDDEN_PARTS or Path(rel).suffix.lower() in FORBIDDEN_EXT:
            raise SystemExit(f"refusing to publish {rel}: game-derived or image/mesh file")
    return out


def set_password():
    pw = os.environ.get("NMS_SITE_PASSWORD")
    if not pw:
        raise SystemExit("set NMS_SITE_PASSWORD in the environment")
    salt = secrets.token_hex(12)
    h = hashlib.sha256(f"{salt}:{pw}".encode("utf-8")).hexdigest()
    GATE_FILE.write_text(json.dumps({"enabled": True, "salt": salt, "hash": h}, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {GATE_FILE} (salt + hash only)")


def public_config(gate_mode):
    src = cards.read_config()
    g = json.loads(GATE_FILE.read_text(encoding="utf-8")) if GATE_FILE.exists() else {"enabled": False}
    enabled = bool(g.get("enabled")) and gate_mode != "off" and bool(g.get("hash"))
    gate = {"enabled": enabled, **({"salt": g["salt"], "hash": g["hash"]} if enabled else {})}
    cfg = {"siteBase": src["siteBase"], "staticSite": True, "noindex": enabled or bool(src.get("noindex", True)), "gate": gate}
    return cfg


def index_html(text, cfg):
    base = cfg["siteBase"]
    og = (f'<meta name="description" content="Predicted derelict freighter layouts for No Man\'s Sky 7.05: crates, footlockers, maps. Unofficial fan project.">\n'
          f'  <meta property="og:type" content="website"><meta property="og:site_name" content="NMS Derelict Atlas">\n'
          f'  <meta property="og:title" content="NMS Derelict Atlas"><meta property="og:description" content="Predicted derelict freighter layouts for No Man\'s Sky 7.05.">\n'
          f'  <meta property="og:url" content="{base}"><meta property="og:image" content="{base}preview.png">\n'
          f'  <meta property="og:image:width" content="{cards.W}"><meta property="og:image:height" content="{cards.H}">\n'
          f'  <meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{base}preview.png">')
    text = text.replace('<meta name="robots" content="noindex">', '<meta name="robots" content="noindex">' if cfg["noindex"] else "")
    return text.replace("<title>Derelict Viewer</title>", "<title>Derelict Viewer</title>\n  " + og, 1)


def robots(cfg):
    return "User-agent: *\nDisallow: /\n" if cfg["noindex"] else "User-agent: *\nAllow: /\n"


def build(atlas, gate_mode=None):
    atlas = Path(atlas)
    cfg = public_config(gate_mode)
    out = {}
    for rel, src in plan().items():
        data = src.read_bytes()
        if rel == "index.html":
            data = index_html(data.decode("utf-8"), cfg).encode("utf-8")
        out[rel] = data
    out["config.js"] = ("window.DV_CONFIG = " + json.dumps(cfg, indent=2) + ";\n").encode("utf-8")
    out["robots.txt"] = robots(cfg).encode("utf-8")
    out[".nojekyll"] = b""
    changed = []
    for rel, data in sorted(out.items()):
        if cards.write_if_changed(atlas / rel, data):
            changed.append(Path(rel))
    return changed, out


def main():
    args = sys.argv[1:]
    if "--set-password" in args:
        return set_password()
    mode = None
    if "--gate" in args:
        i = args.index("--gate")
        mode = args[i + 1]
        del args[i:i + 2]
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    if not args:
        raise SystemExit(__doc__)
    atlas = Path(args[0])
    if check:
        out = {rel: src.read_bytes() for rel, src in plan().items()}
        print(f"whitelist ok: {len(out)} files, {sum(map(len, out.values())) / 1024:.0f} KB")
        return
    changed, out = build(atlas, mode)
    print(f"{atlas}: {len(out)} site files, {sum(map(len, out.values())) / 1024:.1f} KB; {len(changed)} written")


if __name__ == "__main__":
    main()
