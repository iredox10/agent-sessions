import os
import glob
import urllib.parse
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class GrokAdapter(BaseAgentAdapter):
    name = "grok"
    display_name = "Grok"
    cli_binary = "grok"

    def __init__(self):
        super().__init__()
        self.sessions_dir = os.path.expanduser("~/.grok/sessions")

    def is_installed(self) -> bool:
        return os.path.exists(self.sessions_dir) or super().is_installed()

    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        sessions: List[UnifiedSession] = []
        if not os.path.exists(self.sessions_dir):
            return sessions

        norm_folder = self.normalize_cwd(folder_path) if folder_path else None

        for d in glob.glob(os.path.join(self.sessions_dir, "*")):
            if not os.path.isdir(d):
                continue
            dirname = os.path.basename(d)
            decoded_cwd = self.normalize_cwd(urllib.parse.unquote(dirname))
            if norm_folder and decoded_cwd != norm_folder:
                continue

            for sdir in glob.glob(os.path.join(d, "*")):
                bname = os.path.basename(sdir)
                if bname.endswith(".jsonl") or bname.endswith(".sqlite"):
                    continue
                sid = bname
                ts = os.path.getmtime(sdir)
                sessions.append(UnifiedSession(
                    session_id=f"grok:{sid}",
                    native_id=sid,
                    origin_agent="grok",
                    cwd=decoded_cwd,
                    title="Grok Session",
                    created_at=ts,
                    updated_at=ts,
                    turn_count=1,
                    source_file=sdir
                ))
        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        return []

    def write_session(self, session: UnifiedSession) -> bool:
        return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["grok", "resume", session.native_id]
