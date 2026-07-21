# mcmosaic

Convert images and videos into Minecraft block-texture mosaics.

## Why `blocks/` isn't in git

The `blocks/` folder holds Minecraft's own block textures, which aren't ours to
redistribute. `mcmosaic/blocks_fetch.py` populates it automatically the first
time you run any command:

1. It looks for an already-installed Minecraft client jar (official launcher,
   Prism Launcher, MultiMC) and pulls the full, opaque 16x16 block textures
   straight out of it.
2. If nothing local is found, it downloads the official client jar for a given
   version from Mojang's public version manifest (the same endpoint every
   launcher uses) and extracts from that instead.

Either way, nothing gets committed to the repo — `blocks/` stays gitignored
and just gets rebuilt on demand.

## Setup

```bash
git clone <your repo url>
cd mcmosaic
./setup.sh
source venv/bin/activate
```

`setup.sh` installs `ffmpeg` via Homebrew if missing, creates a venv, and
`pip install -e .`s this package so the `mcmosaic` command is on your PATH
inside the venv.

## Usage

```bash
# single image
mcmosaic image input.png output.png

# video, audio is preserved via ffmpeg
mcmosaic video input.mp4 output.mp4

# green-screen video -> transparent PNG frame sequence (for compositing)
mcmosaic video-alpha input.mp4 --frames-dir frames

# force a specific Minecraft version's textures (default: latest release)
mcmosaic image input.png output.png --mc-version 26.1.2

# use a different blocks folder / mosaic width (default width: 72)
mcmosaic video input.mp4 output.mp4 --blocks-dir my_blocks --width 200
```

Run `mcmosaic <command> --help` for the full flag list on each subcommand.