import sqlite3

conn = sqlite3.connect(r"c:\Users\nokturno\Desktop\TRADING PROJECT\trading.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
result = c.fetchall()
print("user_settings table exists:", bool(result))

if not result:
    print("Creating user_settings table...")
    c.execute("""
        CREATE TABLE user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            binance_api_key_enc VARCHAR(500),
            binance_api_secret_enc VARCHAR(500),
            ai_groq_key_enc VARCHAR(500),
            ai_gemini_key_enc VARCHAR(500),
            ai_premium_key_enc VARCHAR(500),
            ai_premium_provider VARCHAR(50),
            ai_premium_base_url VARCHAR(255),
            ai_premium_model VARCHAR(100),
            telegram_chat_id VARCHAR(100),
            telegram_alerts BOOLEAN DEFAULT 0 NOT NULL
        )
    """)
    conn.commit()
    print("Table created successfully")

conn.close()
