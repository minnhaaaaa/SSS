#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
page="$repo_root/docs/demo-video/terminal-demo.html"
runtime_dir="$repo_root/.runtime/demo-video"
frame_dir="$runtime_dir/frames"
manifest="$runtime_dir/frames.txt"
output="$repo_root/docs/demo-video/sss-agent-demo.mp4"

mkdir -p "$frame_dir"
: >"$manifest"

scene=0
while [ "$scene" -lt 6 ]; do
    frame="$frame_dir/scene-$scene.png"
    google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
        --window-size=1440,900 --force-device-scale-factor=1 \
        --screenshot="$frame" "file://$page?scene=$scene" >/dev/null 2>&1
    printf "file '%s'\nduration 7\n" "$frame" >>"$manifest"
    scene=$((scene + 1))
done
printf "file '%s'\n" "$frame_dir/scene-5.png" >>"$manifest"

ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$manifest" \
    -vf "fps=30,format=yuv420p" -c:v libx264 -preset medium -crf 20 \
    -g 30 -keyint_min 30 -sc_threshold 0 \
    -movflags +faststart "$output"

printf '%s\n' "$output"
