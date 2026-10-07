from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

@dataclass
class Turn:
    role: str  # 'user' | 'assistant' | 'system'
    text: str
    timestamp: float = 0.0  # Unix timestamp in seconds
    tool_calls: Optional[List[Dict[str, Any]]] = None

@dataclass
class UnifiedSession:
    session_id: str             # Global unique identifier, e.g. "pi:019f23a3..."
    native_id: str              # Native ID within the harness
    origin_agent: str           # 'agy', 'opencode', 'pi', 'cline', 'cbc', 'cmd', 'copilot', 'codex', etc.
    cwd: str                    # Canonical workspace root / directory
    title: str                  # Short title or initial user prompt preview
    created_at: float           # Unix timestamp in seconds
    updated_at: float           # Unix timestamp in seconds
    turn_count: int = 0
    turns: List[Turn] = field(default_factory=list)
    is_mirror: bool = False     # True if this session was synced/mirrored from another agent
    source_file: str = ""       # Path to session file or SQLite identifier
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_time(self) -> str:
        ts = self.updated_at if self.updated_at > 0 else self.created_at
        if ts > 0:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M")
        return "Unknown"

    @property
    def relative_time(self) -> str:
        ts = self.updated_at if self.updated_at > 0 else self.created_at
        if ts <= 0:
            return "unknown"
        diff = datetime.now().timestamp() - ts
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff // 60)}m ago"
        if diff < 86400:
            return f"{int(diff // 3600)}h ago"
        if diff < 86400 * 30:
            return f"{int(diff // 86400)}d ago"
        return f"{int(diff // (86400 * 30))}mo ago"

    @property
    def clean_title(self) -> str:
        t = self.title.strip().replace("\n", " ")
        if len(t) > 70:
            return t[:67] + "..."
        return t or "Untitled Session"
