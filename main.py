# main.py (modified to include auth_utils and include devices router)
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth_utils import create_user, get_user_by_username, verify_password

# --- Config ---
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "db.sqlite"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static/templates (repo root)
STATIC_DIR = BASE_DIR
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=STATIC_DIR)

# DB init (devices and users)
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            button INTEGER,
            battery INTEGER,
            last_event TEXT,
            online INTEGER,
            location TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_current_user(request: Request):
    username = request.session.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Nu ești autentificat")
    user_row = get_user_by_username(username)
    if not user_row:
        request.session.clear()
        raise HTTPException(status_code=401, detail="User invalid")
    return {"username": user_row["username"], "role": user_row["role"]}

# Ensure admin exists (dev only)
def ensure_admin_exists():
    u = get_user_by_username("admin")
    if not u:
        create_user("admin", "admin123", role="admin")
        print("Admin created with default password 'admin123' - change it immediately!")

ensure_admin_exists()

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username și parola sunt obligatorii")
    user_row = get_user_by_username(username)
    if not user_row or not verify_password(password, user_row["password_hash"]):
        raise HTTPException(status_code=401, detail="Username sau parola incorectă")
    request.session["user"] = user_row["username"]
    return {"role": user_row["role"], "username": user_row["username"]}

@app.post("/api/logout")
async def logout(request: Request):
    request.session.clear()
    return {"detail": "Delogat"}

# Admin endpoints
@app.post("/api/add")
async def add_device(request: Request, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nu ai acces")
    data = await request.json()
    id = data.get("id")
    location = data.get("location")
    if not id or not location:
        raise HTTPException(status_code=400, detail="Completează toate câmpurile")
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO devices (id, button, battery, last_event, online, location) VALUES (?, ?, ?, ?, ?, ?)",
                  (id, 0, 100, None, 1, location))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Device deja existent")
    conn.close()
    return {"detail": "Device adăugat"}

@app.post("/api/resolve/{device_id}")
async def resolve_alarm(device_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nu ai acces")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE devices SET button=0 WHERE id=?", (device_id,))
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Device nu există")
    conn.commit()
    conn.close()
    return {"detail": "Alarma rezolvată"}

@app.delete("/api/delete/{device_id}")
async def delete_device(device_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nu ai acces")
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM devices WHERE id=?", (device_id,))
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Device nu există")
    conn.commit()
    conn.close()
    return {"detail": "Device șters"}

# Include devices router
from devices import router as devices_router
app.include_router(devices_router, prefix="/api", tags=["devices"])

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/index.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nu ai acces")
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})
