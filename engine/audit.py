import time
import threading
from typing import List, Dict, Any

class AuditLogger:
    """
    Thread-safe append-only audit trail logger for hospital spatial transactions.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._logs: List[Dict[str, Any]] = []

    def log(self, action: str, node_id: str, agent_id: str, success: bool, detail: str) -> Dict[str, Any]:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": action.upper(),
            "node_id": node_id,
            "agent_id": agent_id,
            "success": success,
            "detail": detail
        }
        with self._lock:
            self._logs.append(entry)
        return entry

    def get_logs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._logs)
