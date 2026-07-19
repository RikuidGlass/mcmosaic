# mosaithon

Convert images and videos into Minecraft block-texture mosaics.

## Why `blocks/` isn't in git

The `blocks/` folder holds Minecraft's own block textures, which aren't ours to
redistribute. This package now requires you to populate `blocks/` manually with
`.png` textures before running any command.

The package no longer auto-fetches Minecraft assets from local installs or
Mojang's servers.

## Setup

```bash
git clone <your repo url>
cd mcmosaic
./setup.sh
source venv/bin/activate
```

`setup.sh` installs `ffmpeg` and `gh` via Homebrew if missing, creates a
venv, and `pip install -e .`s this package so the `mosaithon` command is on
your PATH inside the venv.

## Usage

```bash
# single image
mosaithon image input.png output.png

# video, audio is preserved via ffmpeg
mosaithon video input.mp4 output.mp4

# green-screen video -> transparent PNG frame sequence (for compositing)
mosaithon video-alpha input.mp4 --frames-dir frames

# use a different blocks folder / mosaic width
mosaithon video input.mp4 output.mp4 --blocks-dir my_blocks --width 200
```

Run `mosaithon <command> --help` for the full flag list on each subcommand.

## Pushing to GitHub with `gh`

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create mosaithon --private --source=. --remote=origin --push
```
