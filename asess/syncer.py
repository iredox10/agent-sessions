import os
import sys
from typing import List, Dict, Optional, Tuple, Any
from asess.models import UnifiedSession
from asess.adapters import get_all_adapters, get_installed_adapters, get_adapter
from asess.adapters.base import BaseAgentAdapter

class SessionSyncer:
    def __init__(self):
        self.adapters = get_installed_adapters()

    def sync_folder(
        self,
        folder_path: str,
        target_agent_names: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Synchronizes all sessions in folder_path across all installed agents.
        Returns summary of synced sessions.
        """
        norm_folder = BaseAgentAdapter.normalize_cwd(folder_path)
        stats = {
            "scanned": 0,
            "originals": 0,
            "mirrored_created": 0,
            "errors": 0,
            "details": []
        }

        # 1. Collect all existing sessions for this folder
        sessions_by_agent: Dict[str, List[UnifiedSession]] = {}
        all_originals: List[UnifiedSession] = []

        for adapter in self.adapters:
            try:
                agent_sessions = adapter.scan_sessions(norm_folder)
                sessions_by_agent[adapter.name] = agent_sessions
                stats["scanned"] += len(agent_sessions)
                for s in agent_sessions:
                    if not s.is_mirror:
                        all_originals.append(s)
            except Exception:
                continue

        stats["originals"] = len(all_originals)

        # 2. Determine target adapters
        target_adapters = []
        for a in self.adapters:
            if target_agent_names and a.name not in target_agent_names:
                continue
            # Adapters that support write_session
            if a.name in ("agy", "opencode", "pi", "cmd", "cbc", "cline", "copilot"):
                target_adapters.append(a)

        # 3. For each original session, check which targets don't have it yet
        for orig in all_originals:
            origin_adapter = get_adapter(orig.origin_agent)
            if not origin_adapter:
                continue

            turns_cached = None

            for target in target_adapters:
                if target.name == orig.origin_agent:
                    continue

                # Check if target already has this session
                existing = sessions_by_agent.get(target.name, [])
                already_has = False
                clean_orig_id = orig.native_id.replace("-", "")[:16]

                for ex in existing:
                    if clean_orig_id in ex.native_id:
                        already_has = True
                        break

                if already_has:
                    continue

                if dry_run:
                    stats["mirrored_created"] += 1
                    stats["details"].append(f"Would sync {orig.origin_agent}:{orig.clean_title} -> {target.name}")
                    continue

                # Load turns once if needed
                if turns_cached is None:
                    try:
                        turns_cached = origin_adapter.load_turns(orig)
                        orig.turns = turns_cached
                    except Exception:
                        turns_cached = []

                if not turns_cached:
                    continue

                try:
                    success = target.write_session(orig)
                    if success:
                        stats["mirrored_created"] += 1
                        stats["details"].append(f"Synced {orig.origin_agent}:{orig.clean_title} -> {target.name}")
                    else:
                        stats["errors"] += 1
                except Exception as e:
                    stats["errors"] += 1

        return stats
