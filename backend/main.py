import asyncio
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.tree_manager import TreeManager, create_default_hospital_tree
from backend.ws_manager import ConnectionManager
from backend.routes import router as api_router

# Initialize Global Arbiter & Connection Manager
root_node = create_default_hospital_tree()
tree_manager = TreeManager(root_node)
ws_manager = ConnectionManager()

async def expired_lock_cleanup_worker():
    """
    Background worker loop running every 1s.
    Checks for expired 30s TTL bed locks, releases them, and broadcasts WS events.
    """
    while True:
        try:
            await asyncio.sleep(1.0)
            expired_events = tree_manager.check_and_expire_locks()
            if expired_events:
                state_update = {
                    "type": "LEASE_EXPIRED",
                    "tree": tree_manager.root.to_dict(),
                    "audit": tree_manager.audit.get_logs(),
                    "detail": expired_events[0]
                }
                await ws_manager.broadcast(state_update)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Cleanup Worker Exception] {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background cleanup task
    cleanup_task = asyncio.create_task(expired_lock_cleanup_worker())
    yield
    # Cancel background task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="VitalGrid — Hospital Spatial Resource Arbiter Engine",
    description="Hierarchical hospital resource locking (Hospital -> Ward -> Dept -> Room -> Bed) with 30s TTL heartbeats.",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router)

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial state upon connection
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "tree": tree_manager.root.to_dict(),
            "audit": tree_manager.audit.get_logs()
        })
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Serve static frontend files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
