import os
import glob
import json
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class AdalAdapter(BaseAgentAdapter):
    name = "adal"
    display_name = "Adal"
    cli_binary = "adal"

    def __init__(self):
        super().__init__()
        self.sessions_dir = os.path.expanduser("~/.adal/sessions")

    def is_installed(self) -> bool:
        return os.path.exists(self.sessions_dir) or super().is_installed()

    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        sessions: List[UnifiedSession] = []
        if not os.path.exists(self.sessions_dir):
            return sessions

        norm_folder = self.normalize_cwd(folder_path) if folder_path else None

        for mfile in glob.glob(os.path.join(self.sessions_dir, "*_metadata.json")):
            try:
                with open(mfile, "r") as fp:
                    meta = json.load(fp)
                sid = meta.get("conversation_id", os.path.basename(mfile).replace("_metadata.json", ""))
                cwd = self.normalize_cwd(meta.get("project_path", ""))
                if norm_folder and cwd != norm_folder:
                    continue

                ts = os.path.getmtime(mfile)
                title = meta.get("last_user_message") or "Adal Session"
                turn_c = meta.get("total_turns", 0)

                sessions.append(UnifiedSession(
                    session_id=f"adal:{sid}",
                    native_id=sid,
                    origin_agent="adal",
                    cwd=cwd,
                    title=title,
                    created_at=ts,
                    updated_at=ts,
                    turn_count=turn_c,
                    source_file=mfile
                ))
            except Exception:
                continue

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        return []

    def write_session(self, session: UnifiedSession) -> bool:
        return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["adal", "resume", session.native_id]
