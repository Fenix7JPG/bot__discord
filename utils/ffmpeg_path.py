# utils/ffmpeg_path.py
import os
import shutil

_local = os.path.abspath(os.path.join(os.path.dirname(__file__), "../commands/music/ffmpeg/ffmpeg.exe"))
FFMPEG_PATH = _local if os.path.isfile(_local) else shutil.which("ffmpeg") or "ffmpeg"

print(f"[ffmpeg] Path: {FFMPEG_PATH}")
print(f"[ffmpeg] Existe: {os.path.isfile(FFMPEG_PATH)}")