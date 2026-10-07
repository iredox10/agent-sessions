import os
import json
import glob
import time
import uuid
from datetime import datetime
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class CmdAdapter(BaseAgentAdapter):
    name = "cmd"
    display_name = "Command Code"
    cli_binary = "cmd"

    def __init__(self):
        super().__init__()
        self.projects_dir = os.path.expanduser("~/.commandcode/projects")

    def is_installed(self) -> bool:
        return os.path.exists(self.projects_dir) or super().is_installed()

    def path_to_slug(self, folder_path: str) -> str:
        norm = self.normalize_cwd(folder_path)
        return norm.strip("/").replace("/", "-").lower()

    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        sessions: List[UnifiedSession] = []
        if not os.path.exists(self.projects_dir):
            return sessions

        if folder_path:
            norm_folder = self.normalize_cwd(folder_path)
            slug = self.path_to_slug(norm_folder)
            target_dirs = [os.path.join(self.projects_dir, slug)]
        else:
            norm_folder = None
            target_dirs = glob.glob(os.path.join(self.projects_dir, "*"))

        for pdir in target_dirs:
            if not os.path.isdir(pdir):
                continue
            for fpath in glob.glob(os.path.join(pdir, "*.jsonl")):
                if fpath.endswith(".checkpoints.jsonl"):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        first_line = fp.readline()
                        if not first_line:
                            continue
                        meta = json.loads(first_line)
                        if meta.get("type") != "session":
                            continue

                        cwd = self.normalize_cwd(meta.get("cwd", ""))
                        if norm_folder and cwd != norm_folder:
                            continue

                        sid = meta.get("id", os.path.basename(fpath).replace(".jsonl", ""))
                        iso_ts = meta.get("timestamp", "")
                        created_ts = 0.0
                        if iso_ts:
                            try:
                                dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
                                created_ts = dt.timestamp()
                            except Exception:
                                pass
                        if created_ts <= 0:
                            created_ts = os.path.getctime(fpath)
                        updated_ts = os.path.getmtime(fpath)

                        title = ""
                        turn_count = 0
                        for line in fp:
                            if not line.strip():
                                continue
                            try:
                                obj = json.loads(line)
                                if obj.get("type") == "message":
                                    msg = obj.get("message", {})
                                    role = msg.get("role", "")
                                    if role in ("user", "assistant"):
                                        turn_count += 1
                                        if role == "user" and not title:
                                            content = msg.get("content", [])
                                            if isinstance(content, list):
                                                for c in content:
                                                    if isinstance(c, dict) and c.get("type") == "text":
                                                        title = c.get("text", "")
                                                        break
                                            elif isinstance(content, str):
                                                title = content
                            except Exception:
                                continue

                        is_mirror = sid.startswith("synced_") or os.path.basename(fpath).startswith("synced_")
                        origin = "cmd"
                        if is_mirror:
                            parts = sid.split("_")
                            if len(parts) >= 2:
                                origin = parts[1]

                        sessions.append(UnifiedSession(
                            session_id=f"cmd:{sid}",
                            native_id=sid,
                            origin_agent=origin,
                            cwd=cwd,
                            title=title or "Command Code Session",
                            created_at=created_ts,
                            updated_at=updated_ts,
                            turn_count=turn_count,
                            is_mirror=is_mirror,
                            source_file=fpath,
                            metadata={"file_path": fpath}
                        ))
                except Exception:
                    continue

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        turns: List[Turn] = []
        fpath = session.metadata.get("file_path") or session.source_file
        if not fpath or not os.path.exists(fpath):
            return turns

        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if obj.get("type") == "message":
                        msg = obj.get("message", {})
                        role = msg.get("role", "user")
                        content = msg.get("content", [])
                        text = ""
                        if isinstance(content, list):
                            text_parts = []
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    text_parts.append(c.get("text", ""))
                            text = "\n".join(text_parts)
                        elif isinstance(content, str):
                            text = content
                        ts = msg.get("timestamp", 0) / 1000.0
                        if text:
                            turns.append(Turn(role=role, text=text, timestamp=ts))
        except Exception:
            pass
        return turns

    def write_session(self, session: UnifiedSession) -> bool:
        try:
            slug = self.path_to_slug(session.cwd)
            target_dir = os.path.join(self.projects_dir, slug)
            os.makedirs(target_dir, exist_ok=True)

            mirror_id = f"synced_{session.origin_agent}_{session.native_id.replace('-', '')[:16]}"
            fpath = os.path.join(target_dir, f"{mirror_id}.jsonl")
            mpath = os.path.join(target_dir, f"{mirror_id}.meta.json")

            with open(fpath, "w", encoding="utf-8") as fp:
                header = {
                    "type": "session",
                    "version": 3,
                    "id": mirror_id,
                    "timestamp": datetime.utcfromtimestamp(session.created_at or time.time()).isoformat() + "Z",
                    "cwd": session.cwd
                }
                fp.write(json.dumps(header) + "\n")

                prev_id = None
                for idx, turn in enumerate(session.turns):
                    msg_id = f"msg_{idx}_{uuid.uuid4().hex[:8]}"
                    ts_iso = datetime.utcfromtimestamp(turn.timestamp or time.time()).isoformat() + "Z"
                    ts_ms = int((turn.timestamp or time.time()) * 1000)
                    msg_data = {
                        "role": turn.role,
                        "content": [{"type": "text", "text": turn.text}],
                        "timestamp": ts_ms
                    }
                    if turn.role == "assistant":
                        msg_data["api"] = "anthropic-messages"
                        msg_data["provider"] = "anthropic"
                        msg_data["model"] = "claude-3-5-sonnet"
                        msg_data["stopReason"] = "endTurn"
                        msg_data["usage"] = {
                            "input": 0,
                            "output": 0,
                            "cacheRead": 0,
                            "cacheWrite": 0,
                            "totalTokens": 0,
                            "cost": {
                                "input": 0.0,
                                "output": 0.0,
                                "cacheRead": 0.0,
                                "cacheWrite": 0.0,
                                "total": 0.0
                            }
                        }

                    line_obj = {
                        "type": "message",
                        "id": msg_id,
                        "parentId": prev_id,
                        "timestamp": ts_iso,
                        "message": msg_data
                    }
                    fp.write(json.dumps(line_obj) + "\n")
                    prev_id = msg_id

            with open(mpath, "w", encoding="utf-8") as fp:
                json.dump({"title": session.title, "synced_from": session.origin_agent}, fp)

            return True
        except Exception:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        if session.source_file and os.path.exists(session.source_file):
            return ["cmd", "--session", session.source_file]
        return ["cmd", "--session", session.native_id]
