import time
import unittest
from asess.models import Turn, UnifiedSession

class TestUnifiedModels(unittest.TestCase):
    def test_turn_creation(self):
        turn = Turn(role="user", text="Hello agent", timestamp=1700000000.0)
        self.assertEqual(turn.role, "user")
        self.assertEqual(turn.text, "Hello agent")
        self.assertEqual(turn.timestamp, 1700000000.0)

    def test_session_properties(self):
        now = time.time()
        session = UnifiedSession(
            session_id="pi:test-123",
            native_id="test-123",
            origin_agent="pi",
            cwd="/tmp/myproject",
            title="Fix authentication bug in navbar component\nwith extra newline",
            created_at=now - 120,
            updated_at=now - 60,
            turn_count=4
        )

        self.assertEqual(session.origin_agent, "pi")
        self.assertEqual(session.cwd, "/tmp/myproject")
        self.assertEqual(session.turn_count, 4)
        self.assertFalse(session.is_mirror)

        # clean_title should strip newlines
        self.assertNotIn("\n", session.clean_title)
        self.assertTrue(session.clean_title.startswith("Fix authentication"))

        # relative_time should be "1m ago"
        self.assertEqual(session.relative_time, "1m ago")

        # formatted_time should be YYYY-MM-DD HH:MM
        self.assertRegex(session.formatted_time, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_clean_title_truncation(self):
        long_title = "A" * 100
        session = UnifiedSession(
            session_id="cline:abc",
            native_id="abc",
            origin_agent="cline",
            cwd="/tmp",
            title=long_title,
            created_at=100.0,
            updated_at=100.0
        )
        self.assertEqual(len(session.clean_title), 70)
        self.assertTrue(session.clean_title.endswith("..."))

if __name__ == "__main__":
    unittest.main()
