import os
import sqlite3
import json
import time
import uuid
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class OpenCodeAdapter(BaseAgentAdapter):
    name = "opencode"
    display_name = "OpenCode"
    cli_binary = "opencode"

    def __init__(self):
        super().__init__()
        self.db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")

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

            query = "SELECT id, project_id, directory, title, time_created, time_updated FROM session WHERE parent_id IS NULL AND (title NOT LIKE '%(@%subagent)%' OR title IS NULL)"
            params = []
            if norm_folder:
                query += " AND directory = ?"
                params = [norm_folder]
            query += " ORDER BY time_updated DESC"

            rows = c.execute(query, params).fetchall()

            for r in rows:
                sid = r["id"]
                cwd = self.normalize_cwd(r["directory"])
                if norm_folder and cwd != norm_folder:
                    continue
                title = r["title"] or "OpenCode Session"
                created_ts = (r["time_created"] or 0) / 1000.0
                updated_ts = (r["time_updated"] or 0) / 1000.0

                is_mirror = sid.startswith("ses_synced_")
                origin = "opencode"
                if is_mirror:
                    parts = sid.split("_")
                    if len(parts) >= 3:
                        origin = parts[2]

                # Get count of turns
                turn_c = c.execute("SELECT COUNT(*) FROM message WHERE session_id = ?", (sid,)).fetchone()[0]

                sessions.append(UnifiedSession(
                    session_id=f"opencode:{sid}",
                    native_id=sid,
                    origin_agent=origin,
                    cwd=cwd,
                    title=title,
                    created_at=created_ts,
                    updated_at=updated_ts,
                    turn_count=turn_c,
                    is_mirror=is_mirror,
                    source_file=self.db_path,
                    metadata={"project_id": r["project_id"]}
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

            messages = c.execute(
                "SELECT id, time_created, data FROM message WHERE session_id = ? ORDER BY time_created ASC",
                (session.native_id,)
            ).fetchall()

            for m in messages:
                mid = m["id"]
                m_data = json.loads(m["data"]) if m["data"] else {}
                role = m_data.get("role", "user")
                ts = (m["time_created"] or 0) / 1000.0

                # Get parts
                parts = c.execute(
                    "SELECT data FROM part WHERE message_id = ? ORDER BY time_created ASC",
                    (mid,)
                ).fetchall()

                text_parts = []
                for p in parts:
                    try:
                        p_data = json.loads(p["data"]) if p["data"] else {}
                        if p_data.get("type") == "text":
                            text_parts.append(p_data.get("text", ""))
                    except Exception:
                        continue

                text = "\n".join(text_parts).strip()
                if not text and "text" in m_data:
                    text = m_data["text"]

                if text:
                    turns.append(Turn(role=role, text=text, timestamp=ts))

            conn.close()
        except Exception:
            pass
        return turns

    def write_session(self, session: UnifiedSession) -> bool:
        if not os.path.exists(self.db_path):
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # Find matching project_id for directory
            p_row = c.execute(
                "SELECT project_id FROM project_directory WHERE directory = ? LIMIT 1",
                (session.cwd,)
            ).fetchone()
            project_id = p_row[0] if p_row else "global"

            mirror_id = f"ses_synced_{session.origin_agent}_{session.native_id.replace('-', '')[:16]}"
            slug = f"synced-{session.origin_agent}-{session.native_id[:8]}"
            title = f"[{session.origin_agent.upper()}] {session.title}"
            created_ms = int((session.created_at or time.time()) * 1000)
            updated_ms = int((session.updated_at or time.time()) * 1000)

            c.execute("""
                INSERT OR REPLACE INTO session
                (id, project_id, directory, path, slug, title, version, cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, tokens_cache_write, agent, model, time_created, time_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0, 0, 0, 0, 0, 'build', '{"id":"synced","providerID":"local"}', ?, ?)
            """, (mirror_id, project_id, session.cwd, session.cwd.strip("/"), slug, title, "1.17.8", created_ms, updated_ms))

            # Delete old messages for this mirror session to avoid duplicates
            c.execute("DELETE FROM part WHERE session_id = ?", (mirror_id,))
            c.execute("DELETE FROM message WHERE session_id = ?", (mirror_id,))

            for idx, turn in enumerate(session.turns):
                msg_id = f"msg_sync_{idx}_{uuid.uuid4().hex[:12]}"
                t_ms = int((turn.timestamp or time.time()) * 1000)
                m_data = json.dumps({"role": turn.role, "time": {"created": t_ms}})
                c.execute("""
                    INSERT INTO message (id, session_id, time_created, time_updated, data)
                    VALUES (?, ?, ?, ?, ?)
                """, (msg_id, mirror_id, t_ms, t_ms, m_data))

                prt_id = f"prt_sync_{idx}_{uuid.uuid4().hex[:12]}"
                p_data = json.dumps({"type": "text", "text": turn.text})
                c.execute("""
                    INSERT INTO part (id, message_id, session_id, time_created, time_updated, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (prt_id, msg_id, mirror_id, t_ms, t_ms, p_data))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["opencode", "-s", session.native_id]
