from fastapi import APIRouter, HTTPException, Depends
from .models import LockRequest, UnlockRequest, HeartbeatRequest, UpgradeRequest
from engine.tree_manager import TreeManager

router = APIRouter(prefix="/api/v1", tags=["Spatial Resource Operations"])

# Dependencies to access TreeManager and ConnectionManager
def get_tree_manager() -> TreeManager:
    from .main import tree_manager
    return tree_manager

def get_ws_manager():
    from .main import ws_manager
    return ws_manager

async def broadcast_state_change(ws_manager, tree_manager, event_type: str, detail: dict):
    """
    Helper function to broadcast updated spatial tree state and audit log to all connected clients.
    """
    payload = {
        "type": event_type,
        "tree": tree_manager.root.to_dict(),
        "audit": tree_manager.audit.get_logs(),
        "detail": detail
    }
    await ws_manager.broadcast(payload)

@router.post("/resource/lock")
async def lock_resource(
    req: LockRequest,
    tm: TreeManager = Depends(get_tree_manager),
    wsm = Depends(get_ws_manager)
):
    ttl = req.ttl_seconds if req.ttl_seconds is not None else 30.0
    success, msg = tm.lock(req.node_id, req.agent_id, ttl)
    if not success:
        raise HTTPException(status_code=409, detail=msg)
    
    await broadcast_state_change(wsm, tm, "LOCK_ACQUIRED", {
        "node_id": req.node_id,
        "agent_id": req.agent_id,
        "message": msg
    })

    return {"success": True, "message": msg, "data": {"node_id": req.node_id, "locked_by": req.agent_id, "ttl_seconds": ttl}}

@router.post("/resource/unlock")
async def unlock_resource(
    req: UnlockRequest,
    tm: TreeManager = Depends(get_tree_manager),
    wsm = Depends(get_ws_manager)
):
    success, msg = tm.unlock(req.node_id, req.agent_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    await broadcast_state_change(wsm, tm, "LOCK_RELEASED", {
        "node_id": req.node_id,
        "agent_id": req.agent_id,
        "message": msg
    })

    return {"success": True, "message": msg, "data": {"node_id": req.node_id}}

@router.post("/resource/heartbeat")
async def heartbeat_resource(
    req: HeartbeatRequest,
    tm: TreeManager = Depends(get_tree_manager),
    wsm = Depends(get_ws_manager)
):
    ttl = req.ttl_seconds if req.ttl_seconds is not None else 30.0
    success, msg = tm.heartbeat(req.node_id, req.agent_id, ttl)
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    await broadcast_state_change(wsm, tm, "HEARTBEAT_RENEWED", {
        "node_id": req.node_id,
        "agent_id": req.agent_id,
        "message": msg
    })

    return {"success": True, "message": msg, "data": {"node_id": req.node_id, "ttl_seconds": ttl}}

@router.post("/resource/upgrade")
async def upgrade_resource(
    req: UpgradeRequest,
    tm: TreeManager = Depends(get_tree_manager),
    wsm = Depends(get_ws_manager)
):
    ttl = req.ttl_seconds if hasattr(req, 'ttl_seconds') and req.ttl_seconds is not None else 30.0
    success, msg = tm.upgrade_lock(req.parent_id, req.agent_id, ttl)
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    await broadcast_state_change(wsm, tm, "LOCK_UPGRADED", {
        "parent_id": req.parent_id,
        "agent_id": req.agent_id,
        "message": msg
    })

    return {"success": True, "message": msg, "data": {"parent_id": req.parent_id}}

@router.get("/resource/status")
def get_status(tm: TreeManager = Depends(get_tree_manager)):
    return {
        "success": True,
        "data": {
            "tree": tm.root.to_dict(),
            "nodes": tm.get_all_nodes_flat()
        }
    }

@router.get("/audit")
def get_audit_trail(tm: TreeManager = Depends(get_tree_manager)):
    return {"success": True, "data": {"log": tm.audit.get_logs()}}
