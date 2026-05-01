import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="AI Meeting Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared Application State (thread-safe via GIL for simple dict mutations)
# ---------------------------------------------------------------------------
_summary_data = {}
_app_state = {
    "current_view": "dashboard",   # dashboard | overlay | summary
    "documents": [],
    "meetings": [],
    "session_active": False,
}

def set_summary_data(data):
    global _summary_data
    _summary_data = data

def set_app_state(key, value):
    _app_state[key] = value

def get_app_state():
    return _app_state

# ---------------------------------------------------------------------------
# WebSocket Manager — for real-time transcript/audio streaming to React
# ---------------------------------------------------------------------------
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = WebSocketManager()

def get_ws_manager():
    return ws_manager

# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/summary")
def get_summary():
    return _summary_data

@app.get("/api/state")
def get_state():
    return _app_state

@app.get("/api/documents")
def get_documents():
    return {"documents": _app_state.get("documents", [])}

@app.get("/api/meetings")
def get_meetings():
    return {"meetings": _app_state.get("meetings", [])}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
    session_dir = app_data / "sessions" / session_id
    if not session_dir.exists():
        return {"error": "Session not found"}
        
    transcript = ""
    transcript_file = session_dir / "transcript.txt"
    if transcript_file.exists():
        with open(transcript_file, "r", encoding="utf-8") as f:
            transcript = f.read()
            
    summary = None
    summary_file = session_dir / "summary.json"
    if summary_file.exists():
        import json
        with open(summary_file, "r", encoding="utf-8") as f:
            try:
                summary = json.load(f)
            except:
                pass
                
    return {
        "id": session_id,
        "transcript": transcript,
        "summary": summary
    }

class NavigateRequest(BaseModel):
    view: str

@app.post("/api/navigate")
def navigate(req: NavigateRequest):
    _app_state["current_view"] = req.view
    return {"status": "ok", "view": req.view}

# ---------------------------------------------------------------------------
# WebSocket Endpoint — React connects here for live updates
# ---------------------------------------------------------------------------
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; we push data from Python signals
            data = await websocket.receive_text()
            # Client can send commands back (e.g., manual query)
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# ---------------------------------------------------------------------------
# SPA Fallback — Serve React build for all non-API routes
# ---------------------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")

# Mount static assets FIRST (js, css, etc.)
if os.path.exists(os.path.join(static_dir, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

# SPA catch-all: serve index.html for all non-API paths
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    # Don't intercept API or WebSocket routes
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        return {"error": "Not found"}
    
    # Try to serve static file first
    file_path = os.path.join(static_dir, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # Fallback to index.html for SPA routing
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Frontend not built. Run 'npm run build' in web/"}
