import os
import sys
import subprocess
from typing import List, Optional, Dict, Tuple
from asess.models import UnifiedSession, Turn
from asess.adapters import get_installed_adapters, get_adapter
from asess.adapters.base import BaseAgentAdapter
from asess.syncer import SessionSyncer

class SessionEngine:
    def __init__(self):
        self.adapters = get_installed_adapters()
        self.syncer = SessionSyncer()

    def list_sessions(
        self,
        folder_path: Optional[str] = None,
        include_mirrors: bool = True,
        agent_filter: Optional[str] = None
    ) -> List[UnifiedSession]:
        norm_folder = BaseAgentAdapter.normalize_cwd(folder_path) if folder_path else None
        results: List[UnifiedSession] = []
        seen_ids = set()

        for adapter in self.adapters:
            if agent_filter and adapter.name.lower() != agent_filter.lower():
                continue
            try:
                sessions = adapter.scan_sessions(norm_folder)
                for s in sessions:
                    if norm_folder and BaseAgentAdapter.normalize_cwd(s.cwd) != norm_folder:
                        continue
                    if not include_mirrors and s.is_mirror:
                        continue
                    if s.session_id in seen_ids:
                        continue
                    seen_ids.add(s.session_id)
                    results.append(s)
            except Exception:
                continue

        # Sort by updated_at descending
        results.sort(key=lambda s: s.updated_at if s.updated_at > 0 else s.created_at, reverse=True)
        return results

    def find_session(self, query: str) -> Optional[Tuple[UnifiedSession, BaseAgentAdapter]]:
        # Query can be "pi:123", "123", "ses_...", etc.
        target_adapter_name = None
        native_query = query
        if ":" in query:
            parts = query.split(":", 1)
            target_adapter_name = parts[0]
            native_query = parts[1]

        for adapter in self.adapters:
            if target_adapter_name and adapter.name.lower() != target_adapter_name.lower():
                continue
            sessions = adapter.scan_sessions()
            for s in sessions:
                if s.session_id == query or s.native_id == native_query or native_query in s.native_id:
                    return s, adapter

        return None

    def resume_session(
        self,
        session_id_or_native_id: str,
        target_agent_name: Optional[str] = None,
        extra_args: Optional[List[str]] = None
    ) -> int:
        match = self.find_session(session_id_or_native_id)
        if not match:
            print(f"Error: Session '{session_id_or_native_id}' not found.", file=sys.stderr)
            return 1

        session, origin_adapter = match
        target_name = (target_agent_name or session.origin_agent).lower()
        target_adapter = get_adapter(target_name)

        if not target_adapter:
            print(f"Error: Target agent '{target_name}' is not recognized.", file=sys.stderr)
            return 1

        if not target_adapter.is_installed():
            print(f"Error: Target agent '{target_adapter.display_name}' ({target_name}) is not installed.", file=sys.stderr)
            return 1

        # If switching agents, ensure target adapter has the session mirrored
        if target_name != session.origin_agent:
            print(f"Bridging session {session.session_id} to {target_adapter.display_name}...")
            turns = origin_adapter.load_turns(session)
            session.turns = turns
            target_adapter.write_session(session)

            # Re-scan target adapter to get mirrored session native ID
            mirrored_sessions = target_adapter.scan_sessions(session.cwd)
            clean_orig_id = session.native_id.replace("-", "")[:16]
            found_mirror = None
            for ms in mirrored_sessions:
                if clean_orig_id in ms.native_id:
                    found_mirror = ms
                    break
            if found_mirror:
                session = found_mirror

        cmd = target_adapter.get_resume_command(session)
        if extra_args:
            cmd.extend(extra_args)

        real_bin = target_adapter.get_binary_path()
        if real_bin and os.path.exists(real_bin):
            cmd[0] = real_bin

        print(f"Launching {target_adapter.display_name}: {' '.join(cmd)}")
        # Change cwd to session workspace if needed
        if session.cwd and os.path.exists(session.cwd):
            try:
                os.chdir(session.cwd)
            except Exception:
                pass

        try:
            # Replace current process or run
            os.execvp(cmd[0], cmd)
        except Exception as e:
            # Fallback to subprocess
            return subprocess.call(cmd)
