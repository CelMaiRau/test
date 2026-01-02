# auth_utils.py
import sqlite3
import os
from datetime import datetime
from passlib.context import CryptContext
from typing import Optional

DB = os.path.join(os.path.dirname(__file__), "db.sqlite")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_user(username: str, password: str, role: str = "user") -> dict:
    hashed = hash_password(password)
    now = datetime.utcnow().isoformat() + "Z"
    with get_db() as db:
        c = db.cursor()
        try:
            c.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                      (username, hashed, role, now))
            db.commit()
            return {"ok": True, "username": username}
        except sqlite3.IntegrityError:
            return {"ok": False, "error": "User deja exista"}

def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT id, username, password_hash, role, created_at FROM users WHERE username=?", (username,))
        return c.fetchone()
