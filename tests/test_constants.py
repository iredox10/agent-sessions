import os
import tempfile
import unittest
from asess.constants import is_asess_wrapper, resolve_real_binary, SUPPORTED_AGENTS

class TestConstants(unittest.TestCase):
    def test_supported_agents_list(self):
        self.assertIn("pi", SUPPORTED_AGENTS)
        self.assertIn("opencode", SUPPORTED_AGENTS)
        self.assertIn("cline", SUPPORTED_AGENTS)
        self.assertIn("cmd", SUPPORTED_AGENTS)
        self.assertIn("agy", SUPPORTED_AGENTS)

    def test_wrapper_detection(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("#!/bin/sh\nexec asess launch pi \"$@\"\n")
            wrapper_path = tf.name

        with tempfile.NamedTemporaryFile("w", delete=False) as tf2:
            tf2.write("#!/bin/sh\necho 'real binary'\n")
            real_path = tf2.name

        try:
            self.assertTrue(is_asess_wrapper(wrapper_path))
            self.assertFalse(is_asess_wrapper(real_path))
            self.assertFalse(is_asess_wrapper("/nonexistent/file/path"))
        finally:
            os.remove(wrapper_path)
            os.remove(real_path)

    def test_env_var_override(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("#!/bin/sh\n")
            custom_bin = tf.name
        os.chmod(custom_bin, 0o755)

        os.environ["ASESS_PI_BIN"] = custom_bin
        try:
            resolved = resolve_real_binary("pi")
            self.assertEqual(resolved, custom_bin)
        finally:
            del os.environ["ASESS_PI_BIN"]
            os.remove(custom_bin)

if __name__ == "__main__":
    unittest.main()
