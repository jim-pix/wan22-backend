import sqlite3
import os
from datetime import date

DB_PATH = os.getenv("DB_PATH", "users.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            token TEXT UNIQUE NOT NULL,
            quota_daily INTEGER DEFAULT 3,
            videos_today INTEGER DEFAULT 0,
            last_reset DATE,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def reset_quota_if_needed(user_id: int, last_reset):
    """Remet le compteur à zéro si on est un nouveau jour"""
    today = date.today().isoformat()
    if str(last_reset) != today:
        conn = get_db()
        conn.execute(
            "UPDATE users SET videos_today = 0, last_reset = ? WHERE id = ?",
            (today, user_id)
        )
        conn.commit()
        conn.close()

def get_user_by_token(token: str):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE token = ? AND active = 1", (token,)
    ).fetchone()
    conn.close()
    return user

def increment_video_count(user_id: int):
    conn = get_db()
    conn.execute(
        "UPDATE users SET videos_today = videos_today + 1, last_reset = ? WHERE id = ?",
        (date.today().isoformat(), user_id)
    )
    conn.commit()
    conn.close()

def create_user(email: str, token: str, quota_daily: int = 3):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (email, token, quota_daily, last_reset) VALUES (?, ?, ?, ?)",
            (email, token, quota_daily, date.today().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def list_users():
    conn = get_db()
    users = conn.execute(
        "SELECT id, email, quota_daily, videos_today, last_reset, active, created_at FROM users"
    ).fetchall()
    conn.close()
    return [dict(u) for u in users]

def deactivate_user(email: str):
    conn = get_db()
    cursor = conn.execute("UPDATE users SET active = 0 WHERE email = ?", (email,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def activate_user(email: str):
    conn = get_db()
    cursor = conn.execute("UPDATE users SET active = 1 WHERE email = ?", (email,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def delete_user(email: str):
    conn = get_db()
    cursor = conn.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def update_quota(email: str, quota_daily: int):
    conn = get_db()
    cursor = conn.execute("UPDATE users SET quota_daily = ? WHERE email = ?", (quota_daily, email))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0
