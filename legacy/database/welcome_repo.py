from database.database import connect



# WELCOME
def set_welcome_channel(guild_id: int, channel_id: int):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO guild_config (guild_id, welcome_channel)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET welcome_channel = excluded.welcome_channel
        """, (guild_id, channel_id))
        conn.commit()

def get_welcome_channel(guild_id: int):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT welcome_channel FROM guild_config
            WHERE guild_id = ?
        """, (guild_id,))
        result = cursor.fetchone()
        return result[0] if result else None

