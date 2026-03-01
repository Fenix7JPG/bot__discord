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
                welcome_channel INTEGER,
                ticket_channel INTEGER
            )
        """)
        conn.commit()