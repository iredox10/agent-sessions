import os
import sqlite3
import time
from datetime import datetime
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class CopilotAdapter(BaseAgentAdapter):
    name = "copilot"
    display_name = "GitHub Copilot"
    cli_binary = "copilot"

    def __init__(self):
        super().__init__()
        self.db_path = os.path.expanduser("~/.copilot/session-store.db")

    def is_installed(self) -> bool:
        return os.path.exists(self.db_path) or super().is_installed()

    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        sessions: List[UnifiedSession] = []
        if not os.path.exists(self.db_path):
            return sessions

        norm_folder = self.normalize_cwd(folder_path) if folder_path else None

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            query = "SELECT id, cwd, summary, created_at, updated_at FROM sessions"
            params = []
            if norm_folder:
                query += " WHERE cwd = ?"
                params = [norm_folder]
            query += " ORDER BY updated_at DESC"

            rows = c.execute(query, params).fetchall()

            for r in rows:
                sid = r["id"]
                cwd = self.normalize_cwd(r["cwd"])
                if norm_folder and cwd != norm_folder:
                    continue
                title = r["summary"] or "Copilot Session"

                created_ts = 0.0
                updated_ts = 0.0
                try:
                    if r["created_at"]:
                        created_ts = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).timestamp()
                    if r["updated_at"]:
                        updated_ts = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass

                turn_c = c.execute("SELECT COUNT(*) FROM turns WHERE session_id = ?", (sid,)).fetchone()[0] * 2

                is_mirror = sid.startswith("synced_") or title.startswith("[")
                origin = "copilot"
                if is_mirror and "_" in sid:
                    origin = sid.split("_")[1]

                sessions.append(UnifiedSession(
                    session_id=f"copilot:{sid}",
                    native_id=sid,
                    origin_agent=origin,
                    cwd=cwd,
                    title=title,
                    created_at=created_ts,
                    updated_at=updated_ts or created_ts,
                    turn_count=turn_c,
                    is_mirror=is_mirror,
                    source_file=self.db_path
                ))
            conn.close()
        except Exception:
            pass

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        turns: List[Turn] = []
        if not os.path.exists(self.db_path):
            return turns

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            rows = c.execute(
                "SELECT turn_index, user_message, assistant_response, timestamp FROM turns WHERE session_id = ? ORDER BY turn_index ASC",
                (session.native_id,)
            ).fetchall()

            for r in rows:
                ts = 0.0
                if r["timestamp"]:
                    try:
                        ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).timestamp()
                    except Exception:
                        pass
                if r["user_message"]:
                    turns.append(Turn(role="user", text=r["user_message"], timestamp=ts))
                if r["assistant_response"]:
                    turns.append(Turn(role="assistant", text=r["assistant_response"], timestamp=ts))

            conn.close()
        except Exception:
            pass
        return turns

    def write_session(self, session: UnifiedSession) -> bool:
        if not os.path.exists(self.db_path):
            return False

        try:
            mirror_id = f"synced_{session.origin_agent}_{session.native_id.replace('-', '')[:16]}"
            iso_created = datetime.utcfromtimestamp(session.created_at or time.time()).isoformat() + "Z"
            iso_updated = datetime.utcfromtimestamp(session.updated_at or time.time()).isoformat() + "Z"
            summary = f"[{session.origin_agent.upper()}] {session.title}"

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute("""
                INSERT OR REPLACE INTO sessions (id, cwd, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (mirror_id, session.cwd, summary, iso_created, iso_updated))

            c.execute("DELETE FROM turns WHERE session_id = ?", (mirror_id,))

            turn_idx = 0
            curr_user = ""
            for turn in session.turns:
                ts_iso = datetime.utcfromtimestamp(turn.timestamp or time.time()).isoformat() + "Z"
                if turn.role == "user":
                    curr_user = turn.text
                elif turn.role == "assistant":
                    c.execute("""
                        INSERT INTO turns (session_id, turn_index, user_message, assistant_response, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, (mirror_id, turn_idx, curr_user, turn.text, ts_iso))
                    turn_idx += 1
                    curr_user = ""

            if curr_user:
                c.execute("""
                    INSERT INTO turns (session_id, turn_index, user_message, assistant_response, timestamp)
                    VALUES (?, ?, ?, '', ?)
                """, (mirror_id, turn_idx, curr_user, iso_updated))

            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["copilot", "sessions", "resume", session.native_id]
