import os
import sqlite3
import json
import time
import uuid
from datetime import datetime
from typing import List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.models import UnifiedSession, Turn

class AgyAdapter(BaseAgentAdapter):
    name = "agy"
    display_name = "Antigravity (AGY)"
    cli_binary = "agy"

    def __init__(self):
        super().__init__()
        self.base_dir = os.path.expanduser("~/.gemini/antigravity-cli")
        self.db_path = os.path.join(self.base_dir, "conversation_summaries.db")
        self.brain_dir = os.path.join(self.base_dir, "brain")

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

            query = """
                SELECT conversation_id, title, preview, step_count, last_modified_time, workspace_uris 
                FROM conversation_summaries 
                WHERE (parent_conversation_id = '' OR parent_conversation_id IS NULL) AND nesting_depth = 0
                ORDER BY last_modified_time DESC
            """
            rows = c.execute(query).fetchall()

            for r in rows:
                cid = r["conversation_id"]
                uris_str = r["workspace_uris"] or "[]"
                try:
                    uris = json.loads(uris_str)
                except Exception:
                    uris = []

                cwd = ""
                for u in uris:
                    if u.startswith("file://"):
                        cwd = self.normalize_cwd(u[7:])
                        break

                if norm_folder and cwd != norm_folder:
                    continue

                title = r["preview"] or r["title"] or "Antigravity Session"
                step_c = r["step_count"] or 0

                created_ts = 0.0
                updated_ts = 0.0
                ltime = r["last_modified_time"] or ""
                if ltime:
                    try:
                        # Some timestamps have nanoseconds or strange formats
                        clean_time = ltime.split(".")[0]
                        if "+" in ltime:
                            tz = ltime[ltime.rfind("+"):]
                            clean_time += tz
                        dt = datetime.fromisoformat(clean_time)
                        updated_ts = dt.timestamp()
                        created_ts = updated_ts
                    except Exception:
                        pass

                tpath = os.path.join(self.brain_dir, cid, ".system_generated/logs/transcript.jsonl")
                if not created_ts and os.path.exists(tpath):
                    created_ts = os.path.getctime(tpath)
                    updated_ts = os.path.getmtime(tpath)

                is_mirror = title.startswith("[") and ("]" in title[:15]) and not title.startswith("[AGY]")
                origin = "agy"
                if is_mirror:
                    tag = title[1:title.index("]")].lower()
                    origin = tag

                sessions.append(UnifiedSession(
                    session_id=f"agy:{cid}",
                    native_id=cid,
                    origin_agent=origin,
                    cwd=cwd,
                    title=title,
                    created_at=created_ts,
                    updated_at=updated_ts or created_ts,
                    turn_count=step_c,
                    is_mirror=is_mirror,
                    source_file=tpath,
                    metadata={"transcript_path": tpath}
                ))

            conn.close()
        except Exception:
            pass

        return sessions

    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        turns: List[Turn] = []
        tpath = session.metadata.get("transcript_path") or session.source_file
        if not tpath or not os.path.exists(tpath):
            tpath = os.path.join(self.brain_dir, session.native_id, ".system_generated/logs/transcript.jsonl")

        if not os.path.exists(tpath):
            return turns

        try:
            with open(tpath, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    stype = obj.get("type", "")
                    content = obj.get("content", "")
                    ts_str = obj.get("created_at", "")
                    ts = 0.0
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                        except Exception:
                            pass

                    if stype == "USER_INPUT" and content:
                        # Clean user request tags if present
                        text = content
                        if "<USER_REQUEST>" in text:
                            start = text.find("<USER_REQUEST>") + len("<USER_REQUEST>")
                            end = text.find("</USER_REQUEST>")
                            text = text[start:end if end != -1 else len(text)].strip()
                        turns.append(Turn(role="user", text=text, timestamp=ts))
                    elif stype == "PLANNER_RESPONSE" and content:
                        turns.append(Turn(role="assistant", text=content, timestamp=ts))
        except Exception:
            pass
        return turns

    def write_session(self, session: UnifiedSession) -> bool:
        if not os.path.exists(self.db_path):
            return False

        try:
            # Deterministic UUID for the mirrored session
            mirror_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{session.origin_agent}:{session.native_id}"))

            log_dir = os.path.join(self.brain_dir, mirror_uuid, ".system_generated/logs")
            os.makedirs(log_dir, exist_ok=True)
            tpath = os.path.join(log_dir, "transcript.jsonl")

            with open(tpath, "w", encoding="utf-8") as fp:
                step_idx = 0
                for turn in session.turns:
                    ts_iso = datetime.utcfromtimestamp(turn.timestamp or time.time()).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if turn.role == "user":
                        entry = {
                            "step_index": step_idx,
                            "source": "USER_EXPLICIT",
                            "type": "USER_INPUT",
                            "status": "DONE",
                            "created_at": ts_iso,
                            "content": f"<USER_REQUEST>\n{turn.text}\n</USER_REQUEST>"
                        }
                    else:
                        entry = {
                            "step_index": step_idx,
                            "source": "MODEL",
                            "type": "PLANNER_RESPONSE",
                            "status": "DONE",
                            "created_at": ts_iso,
                            "content": turn.text
                        }
                    fp.write(json.dumps(entry) + "\n")
                    step_idx += 1

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            preview_text = f"[{session.origin_agent.upper()}] {session.title}"
            workspace_uris = json.dumps([f"file://{session.cwd}"])
            now_iso = datetime.utcfromtimestamp(session.updated_at or time.time()).strftime("%Y-%m-%d %H:%M:%S+00:00")

            c.execute("""
                INSERT OR REPLACE INTO conversation_summaries
                (conversation_id, title, preview, step_count, last_modified_time, workspace_uris, status, source, project_id, agent_name, parent_conversation_id, nesting_depth, battle_id, winning_conversation_id, not_fully_idle, killed, last_user_input_time, last_user_input_step_index, app_data_dir, group_id)
                VALUES (?, '', ?, ?, ?, ?, '', '', '', '', '', 0, '', '', 0, 0, ?, 0, 'antigravity-cli', '')
            """, (mirror_uuid, preview_text, len(session.turns), now_iso, workspace_uris, now_iso))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            return False

    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        return ["agy", "--conversation", session.native_id]
