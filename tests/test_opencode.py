import os
import sqlite3
import json
import tempfile
import unittest
from asess.adapters.opencode import OpenCodeAdapter
from asess.models import UnifiedSession, Turn

class TestOpenCodeAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "opencode.db")
        
        # Initialize an opencode sqlite db with both v1 and v2 schemas
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE session (
                id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT, parent_id TEXT,
                slug TEXT, directory TEXT, path TEXT, title TEXT, version TEXT, share_url TEXT,
                summary_additions INTEGER, summary_deletions INTEGER, summary_files INTEGER,
                summary_diffs TEXT, metadata TEXT, cost REAL, tokens_input INTEGER,
                tokens_output INTEGER, tokens_reasoning INTEGER, tokens_cache_read INTEGER,
                tokens_cache_write INTEGER, revert TEXT, permission TEXT, agent TEXT,
                model TEXT, time_created INTEGER, time_updated INTEGER, time_compacting INTEGER,
                time_archived INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE session_v2 (
                id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT, parent_id TEXT,
                fork_session_id TEXT, fork_boundary TEXT, slug TEXT, directory TEXT,
                path TEXT, title TEXT, version TEXT, share_url TEXT, summary_additions INTEGER,
                summary_deletions INTEGER, summary_files INTEGER, summary_diffs TEXT,
                metadata TEXT, cost REAL, tokens_input INTEGER, tokens_output INTEGER,
                tokens_reasoning INTEGER, tokens_cache_read INTEGER, tokens_cache_write INTEGER,
                revert TEXT, permission TEXT, agent TEXT, model TEXT, time_created INTEGER,
                time_updated INTEGER, time_compacting INTEGER, time_archived INTEGER,
                time_suspended INTEGER, resume_attempts INTEGER, time_idle INTEGER,
                time_viewed INTEGER, idle_outcome TEXT
            )
        """)
        c.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT)")
        c.execute("CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT)")
        c.execute("CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT, type TEXT, seq INTEGER, time_created INTEGER, time_updated INTEGER, data TEXT)")
        c.execute("CREATE TABLE project_directory (project_id TEXT, directory TEXT, type TEXT, strategy TEXT, time_created INTEGER)")
        conn.commit()
        conn.close()

        self.adapter = OpenCodeAdapter()
        self.adapter.db_path = self.db_path

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_write_session_message_schema(self):
        test_session = UnifiedSession(
            session_id="agy:test-session-123",
            native_id="test-session-123",
            origin_agent="agy",
            cwd="/test/path",
            title="Test Session",
            created_at=1000.0,
            updated_at=2000.0,
            turns=[
                Turn(role="user", text="hello world", timestamp=1000.0),
                Turn(role="assistant", text="hi there", timestamp=1001.0),
            ]
        )

        res = self.adapter.write_session(test_session)
        self.assertTrue(res)

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check messages table
        msgs = c.execute("SELECT id, session_id, data FROM message").fetchall()
        self.assertEqual(len(msgs), 2)

        user_data = json.loads(msgs[0][2])
        self.assertEqual(user_data["role"], "user")
        self.assertEqual(user_data["agent"], "build")
        self.assertIn("model", user_data)

        asst_data = json.loads(msgs[1][2])
        self.assertEqual(asst_data["role"], "assistant")
        self.assertEqual(asst_data["mode"], "build")
        self.assertEqual(asst_data["agent"], "build")
        self.assertEqual(asst_data["finish"], "stop")
        self.assertIn("tokens", asst_data)
        self.assertIn("providerID", asst_data)

        # Check session and session_v2 tables
        s1 = c.execute("SELECT id, title, version FROM session").fetchall()
        s2 = c.execute("SELECT id, title, version FROM session_v2").fetchall()
        self.assertEqual(len(s1), 1)
        self.assertEqual(len(s2), 1)
        self.assertIn("[AGY] Test Session", s1[0][1])

        # Check session_message table
        sm = c.execute("SELECT id, type, data FROM session_message ORDER BY seq ASC").fetchall()
        self.assertEqual(len(sm), 2)
        sm_asst = json.loads(sm[1][2])
        self.assertEqual(sm_asst["content"][0]["text"], "hi there")

        conn.close()

    def test_scan_sessions_and_load_turns(self):
        test_session = UnifiedSession(
            session_id="pi:test-pi-1",
            native_id="test-pi-1",
            origin_agent="pi",
            cwd="/test/folder",
            title="Pi Question",
            created_at=1000.0,
            updated_at=2000.0,
            turns=[
                Turn(role="user", text="pi input", timestamp=1000.0),
                Turn(role="assistant", text="pi output", timestamp=1001.0),
            ]
        )
        self.adapter.write_session(test_session)

        sessions = self.adapter.scan_sessions("/test/folder")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].turn_count, 2)

        turns = self.adapter.load_turns(sessions[0])
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].text, "pi input")
        self.assertEqual(turns[1].text, "pi output")

if __name__ == "__main__":
    unittest.main()
