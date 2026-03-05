import sqlite3

DB_NAME = "data/bot.db"

def connect():
    return sqlite3.connect(DB_NAME)


def _setup():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            welcome_channel_id INTEGER,
            ticket_channel_id INTEGER,
            alliance_channel_id INTEGER,
            hunter_role_id INTEGER,
            alliance_role_id INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alliance_ranking (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            points INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

        conn.commit()