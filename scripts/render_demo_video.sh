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
while [ "$scene" -lt 7 ]; do
    case "$scene" in
        0) typing_ms=1500 ;;
        1) typing_ms=2500 ;;
        2) typing_ms=650 ;;
        3) typing_ms=650 ;;
        4) typing_ms=650 ;;
        5) typing_ms=2900 ;;
        *) typing_ms=1300 ;;
    esac

    elapsed=80
    while [ "$elapsed" -le "$typing_ms" ]; do
        frame="$frame_dir/scene-$scene-$elapsed.png"
        google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
            --window-size=1440,900 --force-device-scale-factor=1 \
            --virtual-time-budget="$elapsed" \
            --screenshot="$frame" "file://$page?scene=$scene" >/dev/null 2>&1
        printf "file '%s'\nduration 0.08\n" "$frame" >>"$manifest"
        elapsed=$((elapsed + 80))
    done

    final_frame="$frame_dir/scene-$scene-final.png"
    final_budget=$((typing_ms + 300))
    google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
        --window-size=1440,900 --force-device-scale-factor=1 \
        --virtual-time-budget="$final_budget" \
        --screenshot="$final_frame" "file://$page?scene=$scene" >/dev/null 2>&1
    printf "file '%s'\nduration 4\n" "$final_frame" >>"$manifest"
    scene=$((scene + 1))
done
printf "file '%s'\n" "$frame_dir/scene-6-final.png" >>"$manifest"

ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$manifest" \
    -vf "fps=30,format=yuv420p" -c:v libx264 -preset medium -crf 20 \
    -g 30 -keyint_min 30 -sc_threshold 0 \
    -movflags +faststart "$output"

printf '%s\n' "$output"
