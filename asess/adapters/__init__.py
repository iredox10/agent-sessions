from typing import Dict, List, Optional
from asess.adapters.base import BaseAgentAdapter
from asess.adapters.agy import AgyAdapter
from asess.adapters.opencode import OpenCodeAdapter
from asess.adapters.pi import PiAdapter
from asess.adapters.cline import ClineAdapter
from asess.adapters.cbc import CbcAdapter
from asess.adapters.cmd import CmdAdapter
from asess.adapters.copilot import CopilotAdapter
from asess.adapters.codex import CodexAdapter
from asess.adapters.qwen import QwenAdapter
from asess.adapters.grok import GrokAdapter
from asess.adapters.adal import AdalAdapter

ADAPTER_CLASSES = [
    AgyAdapter,
    OpenCodeAdapter,
    PiAdapter,
    ClineAdapter,
    CbcAdapter,
    CmdAdapter,
    CopilotAdapter,
    CodexAdapter,
    QwenAdapter,
    GrokAdapter,
    AdalAdapter
]

_ADAPTER_INSTANCES: Dict[str, BaseAgentAdapter] = {}

def get_all_adapters() -> List[BaseAgentAdapter]:
    global _ADAPTER_INSTANCES
    if not _ADAPTER_INSTANCES:
        for cls in ADAPTER_CLASSES:
            inst = cls()
            _ADAPTER_INSTANCES[inst.name] = inst
    return list(_ADAPTER_INSTANCES.values())

def get_installed_adapters() -> List[BaseAgentAdapter]:
    return [a for a in get_all_adapters() if a.is_installed()]

def get_adapter(name: str) -> Optional[BaseAgentAdapter]:
    all_ad = get_all_adapters()
    for a in all_ad:
        if a.name.lower() == name.lower():
            return a
    return None
