from database.database import connect

# Establecer canal de alianzas
def set_alianza_channel(guild_id: int, channel_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO guild_config (guild_id, alliance_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET alliance_channel_id = excluded.alliance_channel_id
        """, (guild_id, channel_id))

        conn.commit()

# Establecer rol de alianza
def set_alianza_role(guild_id: int, role_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO guild_config (guild_id, alliance_role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET alliance_role_id = excluded.alliance_role_id
        """, (guild_id, role_id))

        conn.commit()

# Establecer rol de cazador
def set_cazador_role(guild_id: int, role_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO guild_config (guild_id, hunter_role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET hunter_role_id = excluded.hunter_role_id
        """, (guild_id, role_id))

        conn.commit()

# Obtener canal de alianzas
def get_alianza_channel(guild_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT alliance_channel_id
            FROM guild_config
            WHERE guild_id = ?
        """, (guild_id,))

        row = cursor.fetchone()
        return row[0] if row else None
    
# Obtener rol de alianza
def get_alianza_role(guild_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT alliance_role_id
            FROM guild_config
            WHERE guild_id = ?
        """, (guild_id,))

        row = cursor.fetchone()
        return row[0] if row else None

# Obtener rol de cazador
def get_cazador_role(guild_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT hunter_role_id
            FROM guild_config
            WHERE guild_id = ?
        """, (guild_id,))

        row = cursor.fetchone()
        return row[0] if row else None



# sumar punto al cazador
def add_point(guild_id: int, user_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alliance_ranking (guild_id, user_id, points)
            VALUES (?, ?, 1)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET points = points + 1
        """, (guild_id, user_id))

        conn.commit()


# obtener ranking del servidor
def get_ranking(guild_id: int, limit: int = 10):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, points
            FROM alliance_ranking
            WHERE guild_id = ?
            ORDER BY points DESC
            LIMIT ?
        """, (guild_id, limit))

        return cursor.fetchall()


# obtener posicion de un usuario
def get_position(guild_id: int, user_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, points
            FROM alliance_ranking
            WHERE guild_id = ?
            ORDER BY points DESC
        """, (guild_id,))

        ranking = cursor.fetchall()

        for i, (uid, _) in enumerate(ranking, start=1):
            if uid == user_id:
                return i

        return None


# obtener puntos de un usuario específico
def get_points(guild_id: int, user_id: int):
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT points
            FROM alliance_ranking
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))

        result = cursor.fetchone()
        return result[0] if result else 0