import os
import base64

def get_cookies_path():
    # Opción 1: Ruta local (desarrollo)
    local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../cookies.txt"))
    if os.path.exists(local_path):
        return local_path
    
    # Opción 2: Secret Files de Render
    render_secret_path = "/etc/secrets/cookies.txt"
    if os.path.exists(render_secret_path):
        return render_secret_path
    
    # Opción 3: Variable de entorno en Base64
    cookies_b64 = os.environ.get("COOKIES_B64")
    if cookies_b64:
        temp_path = "/tmp/cookies.txt"
        with open(temp_path, "wb") as f:
            f.write(base64.b64decode(cookies_b64))
        return temp_path
    
    raise FileNotFoundError("No se encontró cookies.txt en ninguna ruta")


COOKIES_PATH = get_cookies_path()

# Verificación
first_line = open(COOKIES_PATH).readline()
assert "Netscape HTTP Cookie File" in first_line, f"Archivo inválido: {first_line}"
print(f"✅ Cookies cargadas desde: {COOKIES_PATH}")