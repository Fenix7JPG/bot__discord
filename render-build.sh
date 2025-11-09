# render-build.sh

set -e # Detener el script si un comando falla

# Actualizar la lista de paquetes del sistema operativo
apt-get update

# Instalar FFmpeg sin pedir confirmación (-y)
apt-get install -y ffmpeg