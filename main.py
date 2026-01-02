# backend/main.py
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta

# --- Config ---
DB_FILE = Path(__file__).resolve().parent / "db.sqlite"
PING_TIMEOUT = timedelta(minutes=5)

# --- App ---
app = FastAPI()

# Secret pentru sesiune
app.add_middleware(SessionMiddleware, secret_key="supersecretkey123")

# CORS (optional)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static
BASE_DIR = Path(__file__).resolve().parent.parent  # urcă în BSmart/
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=STATIC_DIR)

# --- Users ---
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"}
}

def get_current_user(request: Request):
    username = request.session.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Nu ești autentificat")
    return USERS.get(username)

# --- DB ---
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
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- API: Login / Logout ---
@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    user = USERS.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Username sau parola incorectă")
    request.session["user"] = username
    return {"role": user["role"], "username": username}

@app.post("/api/logout")
async def logout(request: Request):
    request.session.clear()
    return {"detail": "Delogat"}

# --- API: Devices ---
@app.get("/api/devices")
async def get_devices():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM devices")
    rows = c.fetchall()
    devices = {}
    for row in rows:
        devices[row["id"]] = {
            "button": row["button"],
            "battery": row["battery"],
            "last_event": row["last_event"],
            "online": bool(row["online"]),
            "location": row["location"]
        }
    conn.close()
    return devices

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
                  (id, 0, 100, datetime.now().isoformat(), 1, location))
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
    c.execute("UPDATE devices SET button=1 WHERE id=?", (device_id,))
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
    conn.commit()
    conn.close()
    return {"detail": "Device șters"}

# --- Frontend ---
@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nu ai acces")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})
