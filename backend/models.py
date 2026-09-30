from pydantic import BaseModel, Field
from typing import Optional

class LockRequest(BaseModel):
    node_id: str = Field(..., description="Target spatial node ID (e.g., bed-101A, room-101)")
    agent_id: str = Field(..., description="Staff/Patient/Device agent ID (e.g., dr-smith, nurse-jones)")
    ttl_seconds: Optional[float] = Field(30.0, description="TTL lease duration in seconds")

class UnlockRequest(BaseModel):
    node_id: str = Field(..., description="Target spatial node ID")
    agent_id: str = Field(..., description="Agent attempting to unlock")

class HeartbeatRequest(BaseModel):
    node_id: str = Field(..., description="Target spatial node ID")
    agent_id: str = Field(..., description="Agent extending TTL lease")
    ttl_seconds: Optional[float] = Field(30.0, description="Renewed TTL lease duration")

class UpgradeRequest(BaseModel):
    parent_id: str = Field(..., description="Parent node ID to lock (e.g., room-101)")
    agent_id: str = Field(..., description="Agent claiming parent lock")
