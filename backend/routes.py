from fastapi import APIRouter, HTTPException, Depends
from .models import LockRequest, UnlockRequest, HeartbeatRequest, UpgradeRequest
from engine.tree_manager import TreeManager

router = APIRouter(prefix="/api/v1", tags=["Spatial Resource Operations"])

# Global TreeManager instance injected via app state dependency
def get_tree_manager() -> TreeManager:
    from .main import tree_manager
    return tree_manager

@router.post("/resource/lock")
def lock_resource(req: LockRequest, tm: TreeManager = Depends(get_tree_manager)):
    ttl = req.ttl_seconds if req.ttl_seconds is not None else 30.0
    success, msg = tm.lock(req.node_id, req.agent_id, ttl)
    if not success:
        raise HTTPException(status_code=409, detail=msg)
    return {"success": True, "message": msg, "data": {"node_id": req.node_id, "locked_by": req.agent_id, "ttl_seconds": ttl}}

@router.post("/resource/unlock")
def unlock_resource(req: UnlockRequest, tm: TreeManager = Depends(get_tree_manager)):
    success, msg = tm.unlock(req.node_id, req.agent_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "data": {"node_id": req.node_id}}

@router.post("/resource/heartbeat")
def heartbeat_resource(req: HeartbeatRequest, tm: TreeManager = Depends(get_tree_manager)):
    ttl = req.ttl_seconds if req.ttl_seconds is not None else 30.0
    success, msg = tm.heartbeat(req.node_id, req.agent_id, ttl)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "data": {"node_id": req.node_id, "ttl_seconds": ttl}}

@router.post("/resource/upgrade")
def upgrade_resource(req: UpgradeRequest, tm: TreeManager = Depends(get_tree_manager)):
    ttl = req.ttl_seconds if hasattr(req, 'ttl_seconds') and req.ttl_seconds is not None else 30.0
    success, msg = tm.upgrade_lock(req.parent_id, req.agent_id, ttl)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
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
