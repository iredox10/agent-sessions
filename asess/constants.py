import os
import shutil
from typing import Optional, Dict
from asess.config import get_custom_binary

SUPPORTED_AGENTS = [
    "agy",
    "opencode",
    "pi",
    "cmd",
    "cbc",
    "cline",
    "copilot",
    "codex",
    "qwen",
    "grok",
    "adal"
]

def is_asess_wrapper(file_path: str) -> bool:
    if not file_path or not os.path.isfile(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
            head = fp.read(512)
            return "asess launch" in head or "agent-sessions launch" in head
    except Exception:
        return False

def resolve_real_binary(agent_name: str) -> Optional[str]:
    agent_name = agent_name.lower()

    # 1. Check custom overrides from environment or ~/.config/asess/config.json
    custom = get_custom_binary(agent_name)
    if custom and os.path.isfile(custom) and os.access(custom, os.X_OK):
        return custom

    home = os.path.expanduser("~")

    # 2. Known standard install locations across different package managers
    candidate_paths = [
        os.path.join(home, ".bun", "bin", agent_name),
        os.path.join(home, ".opencode", "bin", agent_name),
        os.path.join(home, ".cargo", "bin", agent_name),
        os.path.join(home, ".local", "lib", "qwen-code", "bin", agent_name),
        os.path.join(home, ".grok", "bin", agent_name),
        os.path.join(home, ".adal", "versions", "current", agent_name),
        os.path.join(home, ".adal", "bin", agent_name),
        os.path.join(home, ".local", "bin", agent_name),
        os.path.join(home, ".npm-global", "bin", agent_name),
        os.path.join(home, ".yarn", "bin", agent_name),
        f"/opt/homebrew/bin/{agent_name}",
        f"/usr/local/bin/{agent_name}",
        f"/usr/bin/{agent_name}",
    ]

    for candidate in candidate_paths:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            if not is_asess_wrapper(candidate):
                return candidate

    # 3. Check system PATH, ensuring we avoid any of our own wrapper scripts
    path_bin = shutil.which(agent_name)
    if path_bin and os.path.isfile(path_bin) and not is_asess_wrapper(path_bin):
        return path_bin

    return None

class _DynamicBinaryMap(dict):
    """A dictionary that dynamically resolves binary paths on access without hardcoded paths."""
    def __getitem__(self, key: str) -> Optional[str]:
        return resolve_real_binary(key)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = resolve_real_binary(key)
        return val if val is not None else default

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return resolve_real_binary(key) is not None

REAL_BINARY_MAP = _DynamicBinaryMap()
