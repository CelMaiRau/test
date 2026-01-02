# devices.py
import sqlite3
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Calea sigură către baza de date (în același folder cu acest fișier)
DB = os.path.join(os.path.dirname(__file__), "db.sqlite")

# Timeout pentru ping
PING_TIMEOUT = timedelta(minutes=10)

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            button INTEGER DEFAULT 1,
            battery INTEGER DEFAULT 100,
            last_event TEXT,
            online INTEGER DEFAULT 1,
            location TEXT
        )
    """)
    db.commit()
    db.close()

init_db()


# --- API --- #

@router.get("/devices")
def get_devices():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, button, battery, last_event, online, location FROM devices")
    rows = c.fetchall()
    db.close()
    devices = {}
    for r in rows:
        last_event = r["last_event"]
        if last_event:
            last_event_dt = datetime.fromisoformat(last_event)
        else:
            last_event_dt = None
        devices[r["id"]] = {
            "button": r["button"],
            "battery": r["battery"],
            "last_event": last_event_dt.isoformat() if last_event_dt else None,
            "online": bool(r["online"]),
            "location": r["location"]
        }
    return devices


@router.post("/add")
def add_device(payload: dict):
    device_id = payload.get("id")
    location = payload.get("location")
    if not device_id or not location:
        raise HTTPException(status_code=400, detail="ID și locație sunt obligatorii")
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO devices (id, location) VALUES (?, ?)", (device_id, location))
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        raise HTTPException(status_code=400, detail="Device deja există")
    db.close()
    return {"detail": f"Device {device_id} adăugat"}

@router.post("/resolve/{device_id}")
def resolve_alarm(device_id: str):
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE devices SET button=1 WHERE id=?", (device_id,))
    db.commit()
    db.close()
    return {"detail": f"Alarma pentru {device_id} a fost rezolvată"}

@router.delete("/delete/{device_id}")
def delete_device(device_id: str):
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM devices WHERE id=?", (device_id,))
    db.commit()
    db.close()
    return {"detail": f"Device {device_id} șters"}

@router.post("/event")
def device_event(payload: dict):
    device_id = payload.get("id")
    button = payload.get("button", 1)
    battery = payload.get("battery", 100)
    db = get_db()
    c = db.cursor()
    c.execute("""
        UPDATE devices 
        SET button=?, battery=?, last_event=?, online=1 
        WHERE id=?
    """, (button, battery, datetime.now().isoformat(), device_id))
    if c.rowcount == 0:
        db.close()
        raise HTTPException(status_code=404, detail="Device nu există")
    db.commit()
    db.close()
    return {"detail": f"Eveniment trimis pentru device {device_id}"}

# Functie optionala: verificare offline după ping timeout
@router.get("/check_offline")
def check_offline():
    now = datetime.now()
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, last_event FROM devices")
    rows = c.fetchall()
    for r in rows:
        last_event = r["last_event"]
        if last_event:
            last_dt = datetime.fromisoformat(last_event)
            if now - last_dt > PING_TIMEOUT:
                c.execute("UPDATE devices SET online=0 WHERE id=?", (r["id"],))
    db.commit()
    db.close()
    return {"detail": "Status device-uri actualizat"}
