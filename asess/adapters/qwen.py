import os
import glob
import json
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class QwenAdapter(BaseAgentAdapter):
    name = "qwen"
    display_name = "Qwen Code"
    cli_binary = "qwen"

    def __init__(self):
        super().__init__()
        self.base_dir = os.path.expanduser("~/.qwen")
        self.projects_dir = os.path.join(self.base_dir, "projects")

    def is_installed(self) -> bool:
        return os.path.exists(self.base_dir) or super().is_installed()

    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        sessions: List[UnifiedSession] = []
        if not os.path.exists(self.projects_dir):
            return sessions

        norm_folder = self.normalize_cwd(folder_path) if folder_path else None

        for pdir in glob.glob(os.path.join(self.projects_dir, "*")):
            chats_dir = os.path.join(pdir, "chats")
            if not os.path.isdir(chats_dir):
                continue
            for rfile in glob.glob(os.path.join(chats_dir, "*.runtime.json")):
                try:
                    with open(rfile, "r") as fp:
                        meta = json.load(fp)
                    sid = meta.get("session_id", os.path.basename(rfile).split(".")[0])
                    cwd = self.normalize_cwd(meta.get("work_dir", ""))
                    if norm_folder and cwd != norm_folder:
                        continue
                    ts = meta.get("started_at", os.path.getmtime(rfile))

                    sessions.append(UnifiedSession(
                        session_id=f"qwen:{sid}",
                        native_id=sid,
                        origin_agent="qwen",
                        cwd=cwd,
                        title="Qwen Code Session",
                        created_at=ts,
                        updated_at=ts,
                        turn_count=1,
                        source_file=rfile
                    ))
                except Exception:
                    continue

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        return []

    def write_session(self, session: UnifiedSession) -> bool:
        return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["qwen", "--resume", session.native_id]
