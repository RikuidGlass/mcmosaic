"""
Validates a local `blocks/` directory of Minecraft block textures.

This package now requires the textures to already exist in `blocks/`.
It will not auto-extract or download Minecraft assets from local installs
or Mojang's servers.
"""
from __future__ import annotations

import os
import sys


def ensure_blocks(out_dir: str = "blocks", mc_version: str | None = None, force: bool = False) -> str:
    """Ensure `out_dir` already contains block texture PNGs."""
    if not os.path.isdir(out_dir):
        raise RuntimeError(
            f"Block textures directory '{out_dir}' not found. "
            "Populate it manually with .png textures; automatic Minecraft fetch is disabled."
        )

    png_files = [f for f in os.listdir(out_dir) if f.lower().endswith(".png")]
    if not png_files:
        raise RuntimeError(
            f"Block textures directory '{out_dir}' contains no .png textures. "
            "Populate it manually with .png textures; automatic Minecraft fetch is disabled."
        )

    return out_dir


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("This script no longer auto-fetches Minecraft textures.")
        sys.exit(1)
    ensure_blocks(force=True)
