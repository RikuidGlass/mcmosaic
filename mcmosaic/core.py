from __future__ import annotations

import os

import numpy as np
from PIL import Image


def average_color(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGB"))
    return np.mean(arr.reshape(-1, 3), axis=0)


def load_blocks(blocks_dir: str):
    """Load every .png in blocks_dir plus its average RGB color."""
    files = [f for f in os.listdir(blocks_dir) if f.lower().endswith(".png")]
    if not files:
        raise FileNotFoundError(f"No .png textures found in '{blocks_dir}'.")

    block_images: dict[str, Image.Image] = {}
    avg_colors = []
    for filename in files:
        path = os.path.join(blocks_dir, filename)
        img = Image.open(path).convert("RGBA")
        name = os.path.splitext(filename)[0]
        block_images[name] = img
        avg_colors.append(average_color(img))

    block_names = list(block_images.keys())
    avg_colors_array = np.array(avg_colors)
    block_size = list(block_images.values())[0].size
    return block_images, block_names, avg_colors_array, block_size


def closest_block(color: np.ndarray, block_names, avg_colors_array: np.ndarray) -> str:
    diffs = np.linalg.norm(avg_colors_array - color, axis=1)
    idx = np.argmin(diffs)
    return block_names[idx]
