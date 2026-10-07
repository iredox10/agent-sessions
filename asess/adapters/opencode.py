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

            existing_tables = set(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())

            session_tables = ["session"]
            if "session_v2" in existing_tables:
                session_tables.append("session_v2")

            seen_rows = {}
            for tbl in session_tables:
                query = f"SELECT id, project_id, directory, title, time_created, time_updated FROM {tbl} WHERE parent_id IS NULL AND (title NOT LIKE '%(@%subagent)%' OR title IS NULL)"
                params = []
                if norm_folder:
                    query += " AND directory = ?"
                    params = [norm_folder]
                query += " ORDER BY time_updated DESC"

                for r in c.execute(query, params).fetchall():
                    sid = r["id"]
                    if sid not in seen_rows or (r["time_updated"] or 0) > (seen_rows[sid]["time_updated"] or 0):
                        seen_rows[sid] = r

            has_session_message = "session_message" in existing_tables
            has_message = "message" in existing_tables

            for sid, r in seen_rows.items():
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

                turn_c = 0
                if has_message:
                    turn_c = c.execute("SELECT COUNT(*) FROM message WHERE session_id = ?", (sid,)).fetchone()[0]
                if turn_c == 0 and has_session_message:
                    turn_c = c.execute("SELECT COUNT(*) FROM session_message WHERE session_id = ?", (sid,)).fetchone()[0]

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

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        turns: List[Turn] = []
        if not os.path.exists(self.db_path):
            return turns

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            existing_tables = set(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())

            if "message" in existing_tables:
                messages = c.execute(
                    "SELECT id, time_created, data FROM message WHERE session_id = ? ORDER BY time_created ASC",
                    (session.native_id,)
                ).fetchall()

                for m in messages:
                    mid = m["id"]
                    m_data = json.loads(m["data"]) if m["data"] else {}
                    role = m_data.get("role", "user")
                    ts = (m["time_created"] or 0) / 1000.0

                    text_parts = []
                    if "part" in existing_tables:
                        parts = c.execute(
                            "SELECT data FROM part WHERE message_id = ? ORDER BY time_created ASC",
                            (mid,)
                        ).fetchall()

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

            # Fallback to session_message for OpenCode 2.0 sessions
            if not turns and "session_message" in existing_tables:
                s_messages = c.execute(
                    "SELECT id, type, time_created, data FROM session_message WHERE session_id = ? ORDER BY seq ASC",
                    (session.native_id,)
                ).fetchall()

                for sm in s_messages:
                    role = sm["type"] or "user"
                    ts = (sm["time_created"] or 0) / 1000.0
                    sm_data = json.loads(sm["data"]) if sm["data"] else {}
                    text = ""
                    if role == "user":
                        text = sm_data.get("text", "")
                    else:
                        content = sm_data.get("content", [])
                        text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                        text = "\n".join(text_parts).strip()

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

            existing_tables = set(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())

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
            """, (mirror_id, project_id, session.cwd, session.cwd.strip("/"), slug, title, "1.18.35", created_ms, updated_ms))

            if "session_v2" in existing_tables:
                c.execute("""
                    INSERT OR REPLACE INTO session_v2
                    (id, project_id, directory, path, slug, title, version, cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, tokens_cache_write, agent, model, time_created, time_updated, resume_attempts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0, 0, 0, 0, 0, 'build', '{"id":"synced","providerID":"local"}', ?, ?, 0)
                """, (mirror_id, project_id, session.cwd, session.cwd.strip("/"), slug, title, "1.18.35", created_ms, updated_ms))

            # Delete old messages for this mirror session to avoid duplicates
            if "part" in existing_tables:
                c.execute("DELETE FROM part WHERE session_id = ?", (mirror_id,))
            if "message" in existing_tables:
                c.execute("DELETE FROM message WHERE session_id = ?", (mirror_id,))
            if "session_message" in existing_tables:
                c.execute("DELETE FROM session_message WHERE session_id = ?", (mirror_id,))

            last_user_msg_id = None
            for idx, turn in enumerate(session.turns):
                msg_id = f"msg_sync_{idx}_{uuid.uuid4().hex[:12]}"
                t_ms = int((turn.timestamp or time.time()) * 1000)
                role = turn.role if turn.role in ("user", "assistant") else "user"

                if role == "assistant":
                    m_data = json.dumps({
                        "parentID": last_user_msg_id,
                        "role": "assistant",
                        "mode": "build",
                        "agent": "build",
                        "path": {"cwd": session.cwd, "root": session.cwd},
                        "cost": 0.0,
                        "tokens": {
                            "total": 0,
                            "input": 0,
                            "output": 0,
                            "reasoning": 0,
                            "cache": {"write": 0, "read": 0}
                        },
                        "modelID": "synced",
                        "providerID": "opencode",
                        "time": {"created": t_ms, "completed": t_ms},
                        "finish": "stop"
                    })
                else:
                    last_user_msg_id = msg_id
                    m_data = json.dumps({
                        "role": "user",
                        "time": {"created": t_ms},
                        "agent": "build",
                        "model": {"providerID": "opencode", "modelID": "synced"},
                        "summary": {"diffs": []}
                    })

                if "message" in existing_tables:
                    c.execute("""
                        INSERT INTO message (id, session_id, time_created, time_updated, data)
                        VALUES (?, ?, ?, ?, ?)
                    """, (msg_id, mirror_id, t_ms, t_ms, m_data))

                if "part" in existing_tables:
                    prt_id = f"prt_sync_{idx}_{uuid.uuid4().hex[:12]}"
                    p_data = json.dumps({
                        "type": "text",
                        "text": str(turn.text or ""),
                        "time": {"start": t_ms, "end": t_ms}
                    })
                    c.execute("""
                        INSERT INTO part (id, message_id, session_id, time_created, time_updated, data)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (prt_id, msg_id, mirror_id, t_ms, t_ms, p_data))

                if "session_message" in existing_tables:
                    if role == "assistant":
                        sm_data = json.dumps({
                            "time": {"created": t_ms, "completed": t_ms},
                            "agent": "build",
                            "model": {"id": "synced", "providerID": "opencode", "variant": "default"},
                            "content": [{"type": "text", "text": str(turn.text or "")}],
                            "finish": "stop",
                            "cost": 0.0,
                            "tokens": {
                                "total": 0,
                                "input": 0,
                                "output": 0,
                                "reasoning": 0,
                                "cache": {"read": 0, "write": 0}
                            }
                        })
                    else:
                        sm_data = json.dumps({
                            "time": {"created": t_ms},
                            "text": str(turn.text or ""),
                            "files": [],
                            "agents": []
                        })
                    c.execute("""
                        INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (msg_id, mirror_id, role, idx, t_ms, t_ms, sm_data))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["opencode", "-s", session.native_id]
