# Contributing to AgentSessionHub (`asess`)

Thank you for your interest in contributing to **AgentSessionHub**! We welcome bug reports, feature suggestions, and contributions for new coding agent adapters.

---

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/iredox10/agent-sessions.git
   cd agent-sessions
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install editable development package**:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run the test suite**:
   ```bash
   python3 -m unittest discover tests
   ```

---

## Adding a New Agent Adapter

Adding support for a new AI coding agent (e.g. Cursor, Aider, OpenDevin, Sweep) takes just a few steps:

1. **Create an Adapter File** in `asess/adapters/<agent_name>.py`:
   ```python
   from typing import List, Optional
   from asess.adapters.base import BaseAgentAdapter
   from asess.models import UnifiedSession, Turn

   class MyAgentAdapter(BaseAgentAdapter):
       name = "myagent"
       display_name = "My Agent"
       cli_binary = "myagent"

       def __init__(self):
           super().__init__()
           self.sessions_dir = os.path.expanduser("~/.myagent/sessions")

       def is_installed(self) -> bool:
           return os.path.exists(self.sessions_dir) or super().is_installed()

       def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
           norm_folder = self.normalize_cwd(folder_path) if folder_path else None
           sessions = []
           # Parse session files, extract workspace cwd, and ensure exact folder match:
           # if norm_folder and cwd != norm_folder: continue
           return sessions

       def load_turns(self, session: UnifiedSession) -> List[Turn]:
           # Parse conversation turns (user prompt, assistant responses)
           return []

       def write_session(self, session: UnifiedSession) -> bool:
           # Write session in native format so foreign sessions can be mirrored/resumed
           return True

       def get_resume_command(self, session: UnifiedSession) -> List[str]:
           # Return command-line arguments to resume the session natively
           return ["myagent", "--resume", session.native_id]
   ```

2. **Register the Adapter** in `asess/adapters/__init__.py`:
   - Import your adapter class.
   - Add it to `ADAPTER_CLASSES`.

3. **Register the Agent** in `SUPPORTED_AGENTS` in `asess/constants.py` and hook templates in `asess/hooks.py`.

4. **Add Unit Tests** in `tests/test_adapters.py`.

---

## Submitting Pull Requests

1. Create a feature branch: `git checkout -b feature/my-new-agent`.
2. Commit your changes: `git commit -m "feat: add support for MyAgent"`.
3. Push to your branch and open a Pull Request against `main`.
4. Ensure all CI tests pass.
