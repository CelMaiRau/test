# devices.py (improved)
import sqlite3
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()

DB = os.path.join(os.path.dirname(__file__), "db.sqlite")
PING_TIMEOUT = timedelta(minutes=10)

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        c = db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                button INTEGER DEFAULT 0,
                battery INTEGER DEFAULT 100,
                last_event TEXT,
                online INTEGER DEFAULT 1,
                location TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                button INTEGER,
                battery INTEGER,
                timestamp TEXT,
                FOREIGN KEY(device_id) REFERENCES devices(id)
            )
        """)
        db.commit()

init_db()

class EventPayload(BaseModel):
    id: str
    button: int = 1
    battery: Optional[int] = 100

def parse_iso(dt_str: Optional[str]) -> Optional[str]:
    if not dt_str:
        return None
    try:
        _ = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt_str
    except Exception:
        return None

@router.get("/devices")
def get_devices() -> List[Dict[str, Any]]:
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT id, button, battery, last_event, online, location FROM devices")
        rows = c.fetchall()
    devices = []
    for r in rows:
        devices.append({
            "id": r["id"],
            "button": r["button"],
            "battery": r["battery"],
            "last_event": parse_iso(r["last_event"]),
            "online": bool(r["online"]),
            "location": r["location"]
        })
    return devices

@router.post("/event")
def device_event(payload: EventPayload):
    device_id = payload.id
    button = int(payload.button)
    battery = int(payload.battery) if payload.battery is not None else 100

    ts = datetime.utcnow().isoformat() + "Z"

    with get_db() as db:
        c = db.cursor()
        c.execute("""
            UPDATE devices 
            SET button=?, battery=?, last_event=?, online=1 
            WHERE id=?
        """, (button, battery, ts, device_id))
        if c.rowcount == 0:
            raise HTTPException(status_code=404, detail="Device nu există")
        c.execute("INSERT INTO events (device_id, button, battery, timestamp) VALUES (?, ?, ?, ?)",
                  (device_id, button, battery, ts))
        db.commit()
    return {"detail": f"Eveniment trimis pentru device {device_id}", "timestamp": ts}

@router.get("/events")
def list_events(limit: int = 200):
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT id, device_id, button, battery, timestamp FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = c.fetchall()
    return [{"id": r["id"], "device_id": r["device_id"], "button": r["button"], "battery": r["battery"], "timestamp": r["timestamp"]} for r in rows]

@router.get("/check_offline")
def check_offline():
    now = datetime.utcnow()
    updated = 0
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT id, last_event FROM devices")
        rows = c.fetchall()
        for r in rows:
            last_event = r["last_event"]
            if last_event:
                try:
                    last_dt = datetime.fromisoformat(last_event.replace("Z", "+00:00"))
                except Exception:
                    last_dt = None
                if (last_dt is None) or (now - last_dt > PING_TIMEOUT):
                    c.execute("UPDATE devices SET online=0 WHERE id=?)", (r["id"],))
                    updated += 1
            else:
                c.execute("UPDATE devices SET online=0 WHERE id=?", (r["id"],))
                updated += 1
        db.commit()
    return {"detail": "Status device-uri actualizat", "updated": updated}
