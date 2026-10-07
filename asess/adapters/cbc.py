import os
import json
import glob
import time
import uuid
from datetime import datetime
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class CbcAdapter(BaseAgentAdapter):
    name = "cbc"
    display_name = "CodeBuddy Code"
    cli_binary = "cbc"

    def __init__(self):
        super().__init__()
        self.projects_dir = os.path.expanduser("~/.codebuddy/projects")

    def is_installed(self) -> bool:
        return os.path.exists(self.projects_dir) or super().is_installed()

    def path_to_slug(self, folder_path: str) -> str:
        norm = self.normalize_cwd(folder_path)
        return norm.strip("/").replace("/", "-")

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
                try:
                    sid = os.path.basename(fpath).replace(".jsonl", "")
                    created_ts = os.path.getctime(fpath)
                    updated_ts = os.path.getmtime(fpath)
                    cwd = ""
                    title = ""
                    turn_count = 0

                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        for line in fp:
                            if not line.strip():
                                continue
                            try:
                                obj = json.loads(line)
                                if not cwd and obj.get("cwd"):
                                    cwd = self.normalize_cwd(obj.get("cwd"))
                                if not title and obj.get("type") == "ai-title":
                                    title = obj.get("aiTitle", "")
                                if obj.get("type") == "message":
                                    role = obj.get("role", "")
                                    if role in ("user", "assistant"):
                                        turn_count += 1
                                        if role == "user" and not title:
                                            cnt = obj.get("content", [])
                                            if isinstance(cnt, list) and cnt:
                                                title = cnt[0].get("text", "")
                            except Exception:
                                continue

                    if not cwd:
                        # Fallback infer from dir name
                        dname = os.path.basename(pdir)
                        cwd = "/" + dname.replace("-", "/")

                    if norm_folder and cwd != norm_folder:
                        continue

                    is_mirror = sid.startswith("synced_")
                    origin = "cbc"
                    if is_mirror:
                        parts = sid.split("_")
                        if len(parts) >= 2:
                            origin = parts[1]

                    sessions.append(UnifiedSession(
                        session_id=f"cbc:{sid}",
                        native_id=sid,
                        origin_agent=origin,
                        cwd=cwd,
                        title=title or "CodeBuddy Session",
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
                        role = obj.get("role", "user")
                        content = obj.get("content", [])
                        text = ""
                        if isinstance(content, list):
                            parts = []
                            for c in content:
                                if isinstance(c, dict) and "text" in c:
                                    parts.append(c["text"])
                            text = "\n".join(parts)
                        elif isinstance(content, str):
                            text = content
                        ts = (obj.get("timestamp") or 0) / 1000.0
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

            with open(fpath, "w", encoding="utf-8") as fp:
                # First user message
                now_ms = int((session.created_at or time.time()) * 1000)
                # ai-title line
                fp.write(json.dumps({
                    "id": str(uuid.uuid4()),
                    "timestamp": now_ms,
                    "type": "ai-title",
                    "aiTitle": f"[{session.origin_agent.upper()}] {session.title}",
                    "sessionId": mirror_id,
                    "cwd": session.cwd
                }) + "\n")

                for idx, turn in enumerate(session.turns):
                    msg_id = f"msg_{idx}_{uuid.uuid4().hex[:8]}"
                    turn_ms = int((turn.timestamp or time.time()) * 1000)
                    msg_obj = {
                        "id": msg_id,
                        "timestamp": turn_ms,
                        "type": "message",
                        "role": turn.role,
                        "content": [{"type": "input_text" if turn.role == "user" else "text", "text": turn.text}],
                        "sessionId": mirror_id,
                        "cwd": session.cwd
                    }
                    fp.write(json.dumps(msg_obj) + "\n")

            return True
        except Exception:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["cbc", "-r", session.native_id]
