import os
import shutil
from abc import ABC, abstractmethod
from typing import List, Optional
from asess.models import UnifiedSession, Turn

class BaseAgentAdapter(ABC):
    name: str = ""
    display_name: str = ""
    cli_binary: str = ""

    def __init__(self):
        self.home = os.path.expanduser("~")

    def is_installed(self) -> bool:
        """Check if binary or storage directory exists on the system."""
        bin_path = self.get_binary_path()
        return bool(bin_path and os.path.exists(bin_path))

    def get_binary_path(self) -> Optional[str]:
        try:
            from asess.constants import REAL_BINARY_MAP
            real = REAL_BINARY_MAP.get(self.name)
            if real and os.path.exists(real):
                return real
        except Exception:
            pass
        if self.cli_binary:
            return shutil.which(self.cli_binary)
        return None

    @staticmethod
    def normalize_cwd(path: Optional[str]) -> str:
        if not path:
            return ""
        return os.path.realpath(os.path.abspath(path))

    @abstractmethod
    def scan_sessions(self, folder_path: Optional[str] = None) -> List[UnifiedSession]:
        """Scan sessions, optionally filtered by folder_path."""
        pass

    @abstractmethod
    def load_turns(self, session: UnifiedSession) -> List[Turn]:
        """Load conversation turns for the given session."""
        pass

    @abstractmethod
    def write_session(self, session: UnifiedSession) -> bool:
        """Write / mirror a foreign session into this agent's native format."""
        pass

    @abstractmethod
    def get_resume_command(self, session: UnifiedSession) -> List[str]:
        """Return the CLI command line arguments to resume this session."""
        pass
