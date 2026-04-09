#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: extract_source_audio.sh <input_video> <output_mp3>" >&2
  exit 2
fi

input_video="$1"
output_mp3="$2"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Error: ffmpeg is required but was not found on PATH." >&2
  exit 1
fi

mkdir -p "$(dirname "$output_mp3")"

ffmpeg -y \
  -i "$input_video" \
  -vn \
  -map a:0 \
  -acodec libmp3lame \
  -q:a 2 \
  "$output_mp3"
