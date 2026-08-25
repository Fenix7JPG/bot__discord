# render-build.sh: se ejecuta en cada despliegue de Render.
set -e

# FFmpeg es necesario para música y radio (audio en vivo).
apt-get update
apt-get install -y ffmpeg
