import os
import glob
import json
import time
from datetime import datetime
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class CodexAdapter(BaseAgentAdapter):
    name = "codex"
    display_name = "Codex"
    cli_binary = "codex"

    def __init__(self):
        super().__init__()
        self.base_dir = os.path.expanduser("~/.codex")
        self.index_path = os.path.join(self.base_dir, "session_index.jsonl")
        self.sessions_dir = os.path.join(self.base_dir, "sessions")

    def is_installed(self) -> bool:
        return os.path.exists(self.base_dir) or super().is_installed()

    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        sessions: List[UnifiedSession] = []
        if not os.path.exists(self.base_dir):
            return sessions

        norm_folder = self.normalize_cwd(folder_path) if folder_path else None

        # Build index map
        title_map = {}
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        if line.strip():
                            obj = json.loads(line)
                            title_map[obj.get("id")] = obj.get("thread_name")
            except Exception:
                pass

        for fpath in glob.glob(os.path.join(self.sessions_dir, "**/*.jsonl"), recursive=True):
            try:
                sid = ""
                cwd = ""
                created_ts = os.path.getctime(fpath)
                updated_ts = os.path.getmtime(fpath)
                turn_c = 0
                title = ""

                # Extract sid from filename, e.g. rollout-...-<uuid>.jsonl
                bname = os.path.basename(fpath).replace(".jsonl", "")
                parts = bname.split("-")
                if len(parts) >= 5:
                    sid = "-".join(parts[-5:])
                else:
                    sid = bname

                title = title_map.get(sid, "")

                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        if not line.strip():
                            continue
                        obj = json.loads(line)
                        if not cwd and "cwd" in obj:
                            cwd = self.normalize_cwd(obj["cwd"])
                        payload = obj.get("payload", {})
                        if not cwd and isinstance(payload, dict):
                            if "cwd" in payload:
                                cwd = self.normalize_cwd(payload["cwd"])
                        if payload.get("type") == "message":
                            role = payload.get("role")
                            if role in ("user", "assistant"):
                                turn_c += 1
                                if role == "user" and not title:
                                    cnt = payload.get("content", [])
                                    if cnt and isinstance(cnt, list) and isinstance(cnt[0], dict):
                                        title = cnt[0].get("text", "")

                if norm_folder and cwd != norm_folder:
                    continue

                sessions.append(UnifiedSession(
                    session_id=f"codex:{sid}",
                    native_id=sid,
                    origin_agent="codex",
                    cwd=cwd,
                    title=title or "Codex Session",
                    created_at=created_ts,
                    updated_at=updated_ts,
                    turn_count=turn_c,
                    source_file=fpath
                ))
            except Exception:
                continue

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        turns: List[Turn] = []
        if not session.source_file or not os.path.exists(session.source_file):
            return turns

        try:
            with open(session.source_file, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    payload = obj.get("payload", {})
                    if payload.get("type") == "message":
                        role = payload.get("role", "user")
                        if role not in ("user", "assistant"):
                            continue
                        content = payload.get("content", [])
                        text = ""
                        if isinstance(content, list):
                            parts = []
                            for c in content:
                                if isinstance(c, dict) and "text" in c:
                                    parts.append(c["text"])
                            text = "\n".join(parts)
                        elif isinstance(content, str):
                            text = content
                        ts = 0.0
                        if "timestamp" in obj:
                            try:
                                ts = datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00")).timestamp()
                            except Exception:
                                pass
                        if text:
                            turns.append(Turn(role=role, text=text, timestamp=ts))
        except Exception:
            pass
        return turns

    def write_session(self, session: UnifiedSession) -> bool:
        # Not primary target for mirrors, but supported if needed
        return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["codex", "--session", session.native_id]
