from database.database import connect
# TICKET
def set_ticket_channel(guild_id: int, channel_id: int):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO guild_config (guild_id, ticket_channel)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET ticket_channel = excluded.ticket_channel
        """, (guild_id, channel_id))
        conn.commit()

def get_ticket_channel(guild_id: int):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticket_channel FROM guild_config
            WHERE guild_id = ?
        """, (guild_id,))
        result = cursor.fetchone()
        return result[0] if result else None