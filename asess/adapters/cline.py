import os
import sqlite3
import json
import time
from datetime import datetime
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class ClineAdapter(BaseAgentAdapter):
    name = "cline"
    display_name = "Cline"
    cli_binary = "cline"

    def __init__(self):
        super().__init__()
        self.data_dir = os.path.expanduser("~/.cline/data")
        self.db_path = os.path.join(self.data_dir, "db/sessions.db")
        self.sessions_dir = os.path.join(self.data_dir, "sessions")

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

            query = "SELECT session_id, cwd, prompt, started_at, updated_at, messages_path FROM sessions WHERE is_subagent = 0"
            params = []
            if norm_folder:
                query += " AND cwd = ?"
                params = [norm_folder]
            query += " ORDER BY updated_at DESC"

            rows = c.execute(query, params).fetchall()

            for r in rows:
                sid = r["session_id"]
                cwd = self.normalize_cwd(r["cwd"])
                if norm_folder and cwd != norm_folder:
                    continue
                prompt = r["prompt"] or ""

                # Extract title from prompt
                title = prompt.replace('<user_input mode="act">', '').replace('<user_input mode="plan">', '').replace('</user_input>', '').strip()
                if not title:
                    title = "Cline Session"

                created_ts = 0.0
                updated_ts = 0.0
                try:
                    if r["started_at"]:
                        created_ts = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00")).timestamp()
                    if r["updated_at"]:
                        updated_ts = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass

                is_mirror = sid.startswith("synced_")
                origin = "cline"
                if is_mirror:
                    parts = sid.split("_")
                    if len(parts) >= 2:
                        origin = parts[1]

                m_path = r["messages_path"] or os.path.join(self.sessions_dir, sid, f"{sid}.messages.json")
                turn_c = 0
                if os.path.exists(m_path):
                    try:
                        with open(m_path, "r", encoding="utf-8", errors="ignore") as mfp:
                            m_obj = json.load(mfp)
                            turn_c = len(m_obj.get("messages", []))
                    except Exception:
                        pass

                sessions.append(UnifiedSession(
                    session_id=f"cline:{sid}",
                    native_id=sid,
                    origin_agent=origin,
                    cwd=cwd,
                    title=title,
                    created_at=created_ts,
                    updated_at=updated_ts or created_ts,
                    turn_count=turn_c,
                    is_mirror=is_mirror,
                    source_file=m_path,
                    metadata={"messages_path": m_path}
                ))
            conn.close()
        except Exception:
            pass

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        turns: List[Turn] = []
        m_path = session.metadata.get("messages_path") or session.source_file
        if not m_path or not os.path.exists(m_path):
            m_path = os.path.join(self.sessions_dir, session.native_id, f"{session.native_id}.messages.json")

        if not os.path.exists(m_path):
            return turns

        try:
            with open(m_path, "r", encoding="utf-8", errors="ignore") as fp:
                data = json.load(fp)
                for msg in data.get("messages", []):
                    role = msg.get("role", "user")
                    content = msg.get("content", [])
                    text = ""
                    if isinstance(content, list):
                        parts = []
                        for c in content:
                            if isinstance(c, dict) and "text" in c:
                                parts.append(c["text"])
                        text = "\n".join(parts)
                    elif isinstance(content, str):
                        text = content
                    ts = (msg.get("ts") or 0) / 1000.0
                    clean_text = text.replace('<user_input mode="act">', '').replace('<user_input mode="plan">', '').replace('</user_input>', '').strip()
                    if clean_text:
                        turns.append(Turn(role=role, text=clean_text, timestamp=ts))
        except Exception:
            pass
        return turns

    def write_session(self, session: UnifiedSession) -> bool:
        if not os.path.exists(self.db_path):
            return False

        try:
            mirror_id = f"synced_{session.origin_agent}_{session.native_id.replace('-', '')[:16]}"
            session_folder = os.path.join(self.sessions_dir, mirror_id)
            os.makedirs(session_folder, exist_ok=True)
            messages_file = os.path.join(session_folder, f"{mirror_id}.messages.json")

            # Write messages json
            messages_list = []
            for idx, turn in enumerate(session.turns):
                t_ms = int((turn.timestamp or time.time()) * 1000)
                messages_list.append({
                    "id": f"msg_{idx}_{mirror_id}",
                    "role": turn.role,
                    "content": [{"type": "text", "text": turn.text}],
                    "ts": t_ms
                })

            with open(messages_file, "w", encoding="utf-8") as fp:
                json.dump({
                    "version": 1,
                    "sessionId": mirror_id,
                    "cwd": session.cwd,
                    "messages": messages_list
                }, fp)

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            iso_created = datetime.utcfromtimestamp(session.created_at or time.time()).isoformat() + "Z"
            iso_updated = datetime.utcfromtimestamp(session.updated_at or time.time()).isoformat() + "Z"
            prompt_text = f"[{session.origin_agent.upper()}] {session.title}"

            c.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, source, pid, started_at, ended_at, exit_code, status, status_lock, interactive, provider, model, cwd, workspace_root, enable_tools, enable_spawn, enable_teams, is_subagent, prompt, transcript_path, hook_path, messages_path, updated_at)
                VALUES (?, 'cli', 0, ?, ?, 0, 'completed', 0, 1, 'cline', 'synced', ?, ?, 1, 1, 1, 0, ?, '', '', ?, ?)
            """, (mirror_id, iso_created, iso_updated, session.cwd, session.cwd, prompt_text, messages_file, iso_updated))

            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["cline", "--id", session.native_id]
