import os
import json
from typing import Dict, Any, Optional

CONFIG_DIR = os.path.expanduser("~/.config/asess")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "binaries": {},
    "default_agent": None,
    "fzf_preview": True,
    "auto_sync": True,
}

_CONFIG_CACHE: Optional[Dict[str, Any]] = None

def get_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    config.update(data)
        except Exception:
            pass

    _CONFIG_CACHE = config
    return _CONFIG_CACHE

def get_custom_binary(agent_name: str) -> Optional[str]:
    # 1. Environment variable override (e.g. ASESS_PI_BIN, ASESS_OPENCODE_BIN)
    env_key = f"ASESS_{agent_name.upper()}_BIN"
    if env_key in os.environ and os.path.exists(os.environ[env_key]):
        return os.environ[env_key]

    # 2. Config file override
    cfg = get_config()
    binaries = cfg.get("binaries", {})
    if agent_name in binaries and os.path.exists(binaries[agent_name]):
        return binaries[agent_name]

    return None

def save_config(new_config: Dict[str, Any]) -> bool:
    global _CONFIG_CACHE
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fp:
            json.dump(new_config, fp, indent=2)
        _CONFIG_CACHE = new_config
        return True
    except Exception:
        return False
