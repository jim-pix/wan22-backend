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
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS loras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'style',
            lora_type TEXT DEFAULT 'standard',
            trigger_words TEXT DEFAULT '[]',
            default_strength REAL DEFAULT 0.8,
            preview_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id TEXT NOT NULL,
            video_url TEXT,
            user_prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Migration : ajoute lora_type si colonne absente (DB existante)
    try:
        conn.execute("ALTER TABLE loras ADD COLUMN lora_type TEXT DEFAULT 'standard'")
        conn.commit()
    except Exception:
        pass

    # Migration : ajoute is_admin si colonne absente (DB existante)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    # S'assurer que l'admin principal a is_admin = 1
    conn.execute("UPDATE users SET is_admin = 1 WHERE email = 'maucerichris@hotmail.com'")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# LORAS
# ─────────────────────────────────────────────

def list_loras(active_only: bool = True):
    conn = get_db()
    query = "SELECT * FROM loras"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name ASC"
    loras = conn.execute(query).fetchall()
    conn.close()
    import json
    result = []
    for l in loras:
        d = dict(l)
        d["trigger_words"] = json.loads(d["trigger_words"] or "[]")
        result.append(d)
    return result


def create_lora(name: str, filename: str, description: str, category: str,
                lora_type: str, trigger_words: list, default_strength: float, preview_url: str = None):
    import json
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO loras (name, filename, description, category, lora_type, trigger_words, default_strength, preview_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, filename, description, category, lora_type, json.dumps(trigger_words), default_strength, preview_url))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def update_lora(lora_id: int, **kwargs):
    import json
    conn = get_db()
    allowed = ["name", "filename", "description", "category", "lora_type", "trigger_words",
               "default_strength", "preview_url", "is_active"]
    fields, values = [], []
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(json.dumps(v) if k == "trigger_words" else v)
    if not fields:
        return False
    values.append(lora_id)
    cursor = conn.execute(f"UPDATE loras SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_lora(lora_id: int):
    conn = get_db()
    cursor = conn.execute("DELETE FROM loras WHERE id = ?", (lora_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_lora_by_id(lora_id: int):
    import json
    conn = get_db()
    lora = conn.execute("SELECT * FROM loras WHERE id = ?", (lora_id,)).fetchone()
    conn.close()
    if not lora:
        return None
    d = dict(lora)
    d["trigger_words"] = json.loads(d["trigger_words"] or "[]")
    return d


# ─────────────────────────────────────────────
# GENERATIONS
# ─────────────────────────────────────────────

def save_generation(user_id: int, job_id: str, video_url: str, user_prompt: str):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO generations (user_id, job_id, video_url, user_prompt)
            VALUES (?, ?, ?, ?)
        """, (user_id, job_id, video_url, user_prompt))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_user_generations(user_id: int, page: int = 1, per_page: int = 12):
    conn = get_db()
    offset = (page - 1) * per_page
    rows = conn.execute("""
        SELECT * FROM generations
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (user_id, per_page, offset)).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM generations WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page)
    }

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

def create_user(email: str, token: str, quota_daily: int = 3, is_admin: int = 0):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (email, token, quota_daily, last_reset, is_admin) VALUES (?, ?, ?, ?, ?)",
            (email, token, quota_daily, date.today().isoformat(), is_admin)
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
        "SELECT id, email, quota_daily, videos_today, last_reset, active, is_admin, created_at FROM users"
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
