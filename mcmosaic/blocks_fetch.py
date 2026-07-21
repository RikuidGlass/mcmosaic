"""
Ensures a local `blocks/` directory of 16x16 Minecraft block textures
exists, fetching it automatically when missing so it never has to be
committed to git.

Resolution order:
1. Look for an already-installed Minecraft client jar (official launcher,
   Prism Launcher, MultiMC, ...) under the usual per-OS install locations
   and pull assets/minecraft/textures/block/*.png straight out of it.
2. If nothing local is found, fetch the client jar for a given version
   (default: latest release) from Mojang's public version manifest -- the
   same endpoint every third-party launcher uses -- and extract from that.

This never bundles or redistributes the textures themselves; it just
automates the same local extraction step a user would otherwise do by hand
from a game install they already own.
"""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import urllib.request
import zipfile

from PIL import Image

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

# Block textures whose filenames don't correspond to a full opaque cube even
# though the PNG itself happens to be fully opaque (slabs, stairs, doors,
# signs, torches, buttons, pressure plates, rails, etc. all reuse a full
# block's texture image but aren't full cubes themselves). This is a
# best-effort denylist by name fragment since shape can't be derived from
# the texture image alone.
_NON_CUBE_NAME_HINTS = (
    "slab", "stairs", "door", "trapdoor", "fence", "wall", "sign", "torch",
    "button", "pressure_plate", "rail", "carpet", "candle", "lantern",
    "campfire", "bed", "banner", "chain", "ladder", "vine", "bars",
    "grate", "coral_fan", "flower_pot", "head", "skull", "lily_pad",
    "sapling", "seagrass", "kelp", "web", "chorus_plant", "chorus_flower",
)

# Non-block-cube utility textures that live in the same folder but should
# never be treated as a paintable block color.
_EXCLUDED_FILENAMES = {"debug.png", "debug2.png"}

_REQUIRED_SIZE = (16, 16)


def _is_fully_opaque(png_bytes: bytes) -> bool:
    """True if the PNG has no translucent/transparent pixels at all."""
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception:
        return False
    alpha = img.getchannel("A")
    lo, hi = alpha.getextrema()
    return lo == 255  # every pixel fully opaque


def _is_correct_size(png_bytes: bytes) -> bool:
    """True if the PNG is exactly 16x16 (rejects animated sheets like 16x64, etc.)."""
    try:
        img = Image.open(io.BytesIO(png_bytes))
        return img.size == _REQUIRED_SIZE
    except Exception:
        return False


def _looks_like_full_cube(name: str) -> bool:
    if name.lower() in _EXCLUDED_FILENAMES:
        return False
    lowered = name.lower()
    return not any(hint in lowered for hint in _NON_CUBE_NAME_HINTS)


def _candidate_launcher_dirs() -> list[str]:
    system = platform.system()
    home = os.path.expanduser("~")
    dirs: list[str] = []
    if system == "Darwin":
        dirs += [
            os.path.join(home, "Library/Application Support/minecraft/versions"),
            os.path.join(home, "Library/Application Support/PrismLauncher/instances"),
            os.path.join(home, "Library/Application Support/MultiMC/instances"),
        ]
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        dirs += [
            os.path.join(appdata, ".minecraft", "versions"),
            os.path.join(appdata, "PrismLauncher", "instances"),
        ]
    else:  # Linux and friends
        dirs += [
            os.path.join(home, ".minecraft", "versions"),
            os.path.join(home, ".local", "share", "PrismLauncher", "instances"),
        ]
    return [d for d in dirs if os.path.isdir(d)]


def _find_local_jars() -> list[tuple[float, str]]:
    """Return (mtime, path) for candidate client jars, newest first."""
    jars: list[tuple[float, str]] = []
    for base in _candidate_launcher_dirs():
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".jar") and not f.endswith("-sources.jar"):
                    path = os.path.join(root, f)
                    try:
                        jars.append((os.path.getmtime(path), path))
                    except OSError:
                        continue
    jars.sort(reverse=True)
    return jars


def _extract_from_jar(jar_path: str, out_dir: str) -> bool:
    try:
        with zipfile.ZipFile(jar_path) as z:
            names = [
                n for n in z.namelist()
                if n.startswith("assets/minecraft/textures/block/") and n.endswith(".png")
            ]
            if not names:
                return False
            os.makedirs(out_dir, exist_ok=True)
            extracted = 0
            skipped = 0
            for n in names:
                base = os.path.basename(n)
                if not _looks_like_full_cube(base):
                    skipped += 1
                    continue
                data = z.read(n)
                if not _is_correct_size(data):
                    skipped += 1
                    continue
                if not _is_fully_opaque(data):
                    skipped += 1
                    continue
                target = os.path.join(out_dir, base)
                with open(target, "wb") as dst:
                    dst.write(data)
                extracted += 1
            print(f"[blocks_fetch] kept {extracted} full opaque 16x16 cube textures, skipped {skipped} (transparent, wrong size, non-cube, or debug)")
            return extracted > 0
    except zipfile.BadZipFile:
        return False


def _download_version_jar(version_id: str | None = None) -> str:
    with urllib.request.urlopen(VERSION_MANIFEST_URL) as r:
        manifest = json.loads(r.read())
    version_id = version_id or manifest["latest"]["release"]
    entry = next((v for v in manifest["versions"] if v["id"] == version_id), None)
    if entry is None:
        raise RuntimeError(f"Version '{version_id}' not found in Mojang's manifest.")
    with urllib.request.urlopen(entry["url"]) as r:
        version_meta = json.loads(r.read())
    client_url = version_meta["downloads"]["client"]["url"]
    tmp_path = os.path.join("/tmp", f"mc_client_{version_id}.jar")
    urllib.request.urlretrieve(client_url, tmp_path)
    return tmp_path


def ensure_blocks(out_dir: str = "blocks", mc_version: str | None = None, force: bool = False) -> str:
    """Make sure `out_dir` contains block textures, fetching them if needed."""
    if not force and os.path.isdir(out_dir) and any(f.endswith(".png") for f in os.listdir(out_dir)):
        return out_dir

    print(f"[blocks_fetch] '{out_dir}' has no textures yet, looking for them...")

    if mc_version is None:
        for _mtime, jar in _find_local_jars():
            if _extract_from_jar(jar, out_dir):
                print(f"[blocks_fetch] extracted textures from local install: {jar}")
                return out_dir
    else:
        print(f"[blocks_fetch] a specific version ({mc_version}) was requested, skipping local jar scan")

    print(f"[blocks_fetch] downloading the official client jar from Mojang ({mc_version or 'latest release'})...")
    jar = _download_version_jar(mc_version)
    if _extract_from_jar(jar, out_dir):
        print(f"[blocks_fetch] extracted textures from downloaded jar: {jar}")
        return out_dir

    raise RuntimeError("Could not locate or extract block textures from any jar.")


if __name__ == "__main__":
    version_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ensure_blocks(mc_version=version_arg, force=True)