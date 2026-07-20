from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

from .blocks_fetch import ensure_blocks
from .core import average_color, closest_block, load_blocks  # noqa: F401 (average_color kept for reuse)


# ---------------------------------------------------------------------------
# image
# ---------------------------------------------------------------------------
def cmd_image(args: argparse.Namespace) -> None:
    ensure_blocks(args.blocks_dir, mc_version=args.mc_version)
    block_images, block_names, avg_colors_array, block_size = load_blocks(args.blocks_dir)
    block_w, block_h = block_size

    img = Image.open(args.input).convert("RGB")
    w, h = img.size
    new_h = max(1, int(h * args.width / w))
    small = img.resize((args.width, new_h), Image.Resampling.LANCZOS)
    small_arr = np.array(small)

    out = Image.new("RGB", (args.width * block_w, new_h * block_h))
    for y in tqdm(range(new_h), desc="PROCESSING", unit="row"):
        for x in range(args.width):
            color = small_arr[y, x, :3].astype(float)
            name = closest_block(color, block_names, avg_colors_array)
            out.paste(block_images[name].convert("RGB"), (x * block_w, y * block_h))

    out.save(args.output)
    print(f"Saved: {args.output}")


# ---------------------------------------------------------------------------
# video (full mosaic, no transparency)
# ---------------------------------------------------------------------------
def _process_frame_full(args_tuple):
    frame, block_images, block_names, avg_colors_array, block_size, width = args_tuple
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    w, h = img.size
    new_h = max(1, int(h * width / w))
    small = img.resize((width, new_h), Image.Resampling.LANCZOS)
    small_arr = np.array(small)

    block_w, block_h = block_size
    out = Image.new("RGB", (width * block_w, new_h * block_h))
    for y in range(new_h):
        for x in range(width):
            color = small_arr[y, x, :3].astype(float)
            name = closest_block(color, block_names, avg_colors_array)
            out.paste(block_images[name].convert("RGB"), (x * block_w, y * block_h))
    return cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR)


def cmd_video(args: argparse.Namespace) -> None:
    ensure_blocks(args.blocks_dir, mc_version=args.mc_version)
    block_images, block_names, avg_colors_array, block_size = load_blocks(args.blocks_dir)

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        sys.exit(f"ERROR: could not open '{args.input}'")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        sys.exit("ERROR: could not read frame count")

    silent_path = args.output + ".silent.mp4" if not args.no_audio else args.output
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    writer = None
    futures = []
    num_workers = max(1, os.cpu_count() // 2)

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        with tqdm(total=frame_count, desc="PROCESSING", unit="frame") as pbar:
            def flush_one():
                nonlocal writer
                done = futures.pop(0)
                mosaic = done.result()
                if writer is None:
                    h, w, _ = mosaic.shape
                    writer = cv2.VideoWriter(silent_path, fourcc, fps, (w, h))
                writer.write(mosaic)
                pbar.update(1)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                futures.append(executor.submit(
                    _process_frame_full,
                    (frame, block_images, block_names, avg_colors_array, block_size, args.width),
                ))
                if len(futures) >= num_workers:
                    flush_one()
            while futures:
                flush_one()

    cap.release()
    if writer:
        writer.release()

    if args.no_audio:
        print(f"Saved: {args.output}")
        return

    print("Video stream done, merging original audio with ffmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-i", silent_path,
        "-i", args.input,
        "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v:0", "-map", "1:a:0",
        args.output,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(silent_path)
        print(f"Saved: {args.output}")
    except FileNotFoundError:
        print("ffmpeg not found (install it: brew install ffmpeg). Silent video kept at:", silent_path)
    except subprocess.CalledProcessError:
        print("ffmpeg audio merge failed. Silent video kept at:", silent_path)


# ---------------------------------------------------------------------------
# video-alpha (green-screen -> transparent PNG frame sequence)
# ---------------------------------------------------------------------------
def _is_green(r, g, b, h_min, h_max, s_min, v_min) -> bool:
    hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = hsv
    return (h_min <= h <= h_max) and (s >= s_min) and (v >= v_min)


def _process_frame_alpha(args_tuple):
    index, frame, block_images, block_names, avg_colors_array, block_size, width, frames_dir, key = args_tuple
    h_min, h_max, s_min, v_min = key
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    w, h = img.size
    new_h = max(1, int(h * width / w))
    small = img.resize((width, new_h), Image.Resampling.LANCZOS)
    small_arr = np.array(small)

    block_w, block_h = block_size
    out = Image.new("RGBA", (width * block_w, new_h * block_h), (0, 0, 0, 0))
    for y in range(new_h):
        for x in range(width):
            r, g, b = small_arr[y, x]
            if _is_green(r, g, b, h_min, h_max, s_min, v_min):
                continue  # leave transparent
            color = np.array([r, g, b], dtype=float)
            name = closest_block(color, block_names, avg_colors_array)
            tile = block_images[name]
            out.paste(tile, (x * block_w, y * block_h), tile)
    out.save(os.path.join(frames_dir, f"frame_{index:05d}.png"))
    return True


def cmd_video_alpha(args: argparse.Namespace) -> None:
    ensure_blocks(args.blocks_dir, mc_version=args.mc_version)
    block_images, block_names, avg_colors_array, block_size = load_blocks(args.blocks_dir)
    os.makedirs(args.frames_dir, exist_ok=True)

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        sys.exit(f"ERROR: could not open '{args.input}'")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        sys.exit("ERROR: could not read frame count")

    key = (args.hue_min, args.hue_max, args.sat_min, args.val_min)
    num_workers = max(1, os.cpu_count() // 2)
    futures = []
    index = 0

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        with tqdm(total=frame_count, desc="PROCESSING", unit="frame") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                futures.append(executor.submit(
                    _process_frame_alpha,
                    (index, frame, block_images, block_names, avg_colors_array, block_size,
                     args.width, args.frames_dir, key),
                ))
                index += 1
                if len(futures) >= num_workers:
                    futures.pop(0).result()
                    pbar.update(1)
            while futures:
                futures.pop(0).result()
                pbar.update(1)

    cap.release()
    print(f"Saved {index} transparent frames to: {args.frames_dir}")


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--blocks-dir", default="blocks", help="folder to auto-populate/read block textures from (default: blocks)")
    common.add_argument("--mc-version", default=None, help="Minecraft version to pull textures from if none are found locally (default: latest release)")

    p = argparse.ArgumentParser(prog="mcmosaic", description="Turn images/videos into Minecraft block-texture mosaics", parents=[common])
    sub = p.add_subparsers(dest="command", required=True)

    p_img = sub.add_parser("image", help="convert a single image", parents=[common])
    p_img.add_argument("input")
    p_img.add_argument("output")
    p_img.add_argument("--width", type=int, default=144)
    p_img.set_defaults(func=cmd_image)

    p_vid = sub.add_parser("video", help="convert a video, keeping its audio", parents=[common])
    p_vid.add_argument("input")
    p_vid.add_argument("output")
    p_vid.add_argument("--width", type=int, default=144)
    p_vid.add_argument("--no-audio", action="store_true", help="skip the ffmpeg audio merge step")
    p_vid.set_defaults(func=cmd_video)

    p_alpha = sub.add_parser("video-alpha", help="convert a green-screen video to a transparent PNG frame sequence", parents=[common])
    p_alpha.add_argument("input")
    p_alpha.add_argument("--frames-dir", default="frames")
    p_alpha.add_argument("--width", type=int, default=144)
    p_alpha.add_argument("--hue-min", type=int, default=35)
    p_alpha.add_argument("--hue-max", type=int, default=85)
    p_alpha.add_argument("--sat-min", type=int, default=50)
    p_alpha.add_argument("--val-min", type=int, default=50)
    p_alpha.set_defaults(func=cmd_video_alpha)

    return p


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
