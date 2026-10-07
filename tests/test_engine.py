import tempfile
import unittest
from asess.engine import SessionEngine
from asess.models import UnifiedSession

class TestSessionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SessionEngine()

    def test_engine_initialization(self):
        from asess.adapters import get_all_adapters
        self.assertGreater(len(get_all_adapters()), 0)
        self.assertIsInstance(self.engine.adapters, list)

    def test_exact_folder_filtering_empty_directory(self):
        # A fresh empty directory must return exactly 0 sessions
        with tempfile.TemporaryDirectory() as tmpdir:
            sessions = self.engine.list_sessions(folder_path=tmpdir, include_mirrors=False)
            self.assertEqual(len(sessions), 0)

    def test_find_nonexistent_session(self):
        match = self.engine.find_session("nonexistent-uuid-99999")
        self.assertIsNone(match)

if __name__ == "__main__":
    unittest.main()
