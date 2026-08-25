import sqlite3
import os

def export_db_to_txt(db_path, output_name="resumen_db.txt"):
    # Carpeta del script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_txt = os.path.join(base_dir, output_name)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Obtener todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]

        with open(output_txt, 'w', encoding='utf-8') as f:
            for table in tables:
                f.write(f"Tabla: {table}\n")

                # Columnas
                cursor.execute(f"PRAGMA table_info({table});")
                columns = [col[1] for col in cursor.fetchall()]
                f.write("Columnas: " + ", ".join(columns) + "\n")

                # Filas (máx 4, si hay más poner '...')
                cursor.execute(f"SELECT * FROM {table} LIMIT 5;")
                rows = cursor.fetchall()
                for i, row in enumerate(rows):
                    if i < 4:
                        f.write(str(row) + "\n")
                    else:
                        f.write("...\n")
                        break
                f.write("\n")  # Separador entre tablas

    print(f"Exportación completa en {output_txt}")

# Ejemplo de uso
export_db_to_txt("data/bot.db")