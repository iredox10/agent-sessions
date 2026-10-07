import os
import sys
import argparse
import json
import signal
import shutil

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except Exception:
    pass

from asess.constants import REAL_BINARY_MAP
from asess.engine import SessionEngine
from asess.syncer import SessionSyncer
from asess.ui import InteractiveUI
from asess.hooks import get_hook_script, install_hooks, uninstall_hooks
from asess.adapters import get_all_adapters, get_installed_adapters, get_adapter

def handle_launch(agent_name: str, agent_args: list):
    agent_name = agent_name.lower()
    real_bin = REAL_BINARY_MAP.get(agent_name)
    if not real_bin or not os.path.exists(real_bin):
        adapter = get_adapter(agent_name)
        real_bin = adapter.get_binary_path() if adapter else shutil.which(agent_name)

    if not real_bin or not os.path.exists(real_bin):
        print(f"Error: binary for agent '{agent_name}' not found.", file=sys.stderr)
        sys.exit(1)

    # 1. IMMEDIATE PASS-THROUGH:
    # If any flags or arguments are supplied (e.g. pi --version, cmd "prompt", cbc -v),
    # immediately execvp the real binary with ZERO delay and zero scanning.
    if agent_args:
        os.execvp(real_bin, [real_bin] + agent_args)
        return

    # 2. Non-interactive check: if stdin is not a tty, launch fresh session directly
    if not sys.stdin.isatty():
        os.execvp(real_bin, [real_bin])
        return

    # 3. Interactive launch with NO arguments:
    # Scan for past sessions in the current workspace across all agent harnesses
    engine = SessionEngine()
    ui = InteractiveUI(engine)
    current_folder = os.getcwd()
    sessions = engine.list_sessions(current_folder, include_mirrors=False)

    # 4. If no past sessions found in this folder, launch fresh session immediately!
    if not sessions:
        os.execvp(real_bin, [real_bin])
        return

    # 5. Sessions exist in this workspace! Present interactive session picker
    selected = ui.run_agent_launch_picker(agent_name, sessions)
    if selected is None:
        # User selected [+ Start a new session] or hit 'n' / ESC
        os.execvp(real_bin, [real_bin])
    else:
        # User selected an existing session to resume
        engine.resume_session(selected.session_id, target_agent_name=agent_name)

def main():
    # Fast path for 'asess launch <agent> ...' before parsing full argparse
    if len(sys.argv) > 1 and sys.argv[1] == "launch":
        if len(sys.argv) < 3:
            print("Usage: asess launch <agent> [args...]", file=sys.stderr)
            sys.exit(1)
        handle_launch(sys.argv[2], sys.argv[3:])
        return

    parser = argparse.ArgumentParser(
        prog="asess",
        description="AgentSessionHub — Unified Cross-Agent Session History & Resuming Hub"
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    # Global flags on root
    parser.add_argument("-a", "--all", action="store_true", help="Include all workspaces instead of just current directory")
    parser.add_argument("-d", "--dir", type=str, default=None, help="Target directory (defaults to current working directory)")

    # 1. list
    list_parser = subparsers.add_parser("list", help="List sessions in workspace or globally")
    list_parser.add_argument("-d", "--dir", type=str, default=None, help="Filter by folder (defaults to current directory)")
    list_parser.add_argument("-a", "--all", action="store_true", help="List all sessions across all workspaces")
    list_parser.add_argument("--agent", type=str, default=None, help="Filter by origin agent (e.g. agy, opencode, pi)")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.add_argument("--no-mirrors", action="store_true", help="Exclude mirrored sessions")

    # 2. sync
    sync_parser = subparsers.add_parser("sync", help="Synchronize sessions across all coding agents in the workspace")
    sync_parser.add_argument("-d", "--dir", type=str, default=None, help="Target folder to sync (defaults to current directory)")
    sync_parser.add_argument("-a", "--all", action="store_true", help="Sync all known workspaces")
    sync_parser.add_argument("--targets", type=str, default=None, help="Comma-separated target agents (e.g. agy,opencode,pi,cbc,cmd,cline)")
    sync_parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without writing")
    sync_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output (used for shell hooks)")

    # 3. resume
    resume_parser = subparsers.add_parser("resume", help="Resume a session in its native agent or any other harness")
    resume_parser.add_argument("session_id", type=str, help="Session ID or partial UUID to resume")
    resume_parser.add_argument("--agent", type=str, default=None, help="Resume with a specific agent (e.g. agy, opencode, pi, cbc, cmd, cline)")
    resume_parser.add_argument("extra_args", nargs="*", help="Extra arguments passed to the agent CLI")

    # 4. preview
    preview_parser = subparsers.add_parser("preview", help="Render formatted preview of a session")
    preview_parser.add_argument("session_id", type=str, help="Session ID to preview")

    # 5. init
    init_parser = subparsers.add_parser("init", help="Generate shell integration code")
    init_parser.add_argument("shell", nargs="?", default="zsh", choices=["zsh", "bash"], help="Shell type")

    # 6. install-hooks
    subparsers.add_parser("install-hooks", help="Install auto-sync shell hooks into ~/.zshrc and ~/.bashrc")

    # 7. uninstall-hooks
    subparsers.add_parser("uninstall-hooks", help="Remove auto-sync shell hooks from ~/.zshrc and ~/.bashrc")

    # 8. launch (Smart agent launcher: checks for sessions in folder)
    launch_parser = subparsers.add_parser("launch", help="Smart launcher for an agent harness with session awareness")
    launch_parser.add_argument("agent", type=str, help="Agent to launch (e.g. pi, cmd, cbc, cline, agy, opencode)")
    launch_parser.add_argument("agent_args", nargs="*", help="Arguments passed to the agent")

    # 9. info
    subparsers.add_parser("info", help="Show installed agent harnesses and session statistics")

    args = parser.parse_args()
    engine = SessionEngine()
    ui = InteractiveUI(engine)
    syncer = SessionSyncer()

    # If no subcommand, launch interactive UI
    if not args.subcommand:
        ui.run_fzf(folder_path=args.dir, all_workspaces=args.all)
        return

    if args.subcommand == "list":
        folder = None if args.all else (args.dir or os.getcwd())
        sessions = engine.list_sessions(
            folder_path=folder,
            include_mirrors=not args.no_mirrors,
            agent_filter=args.agent
        )

        if args.json:
            out = []
            for s in sessions:
                out.append({
                    "session_id": s.session_id,
                    "native_id": s.native_id,
                    "origin_agent": s.origin_agent,
                    "cwd": s.cwd,
                    "title": s.title,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "formatted_time": s.formatted_time,
                    "turn_count": s.turn_count,
                    "is_mirror": s.is_mirror,
                    "source_file": s.source_file
                })
            print(json.dumps(out, indent=2))
        else:
            if not sessions:
                print(f"No sessions found for {'all workspaces' if args.all else (folder or os.getcwd())}.")
                return

            print(f"\033[1;36mFound {len(sessions)} sessions in {'all workspaces' if args.all else (folder or os.getcwd())}:\033[0m\n")
            print(f" {'ID':<38}  {'AGENT':<10}  {'UPDATED':<16}  {'TURNS':<6}  {'TITLE'}")
            print(" " + "─" * 105)
            for s in sessions:
                tag = f"[{s.origin_agent}]"
                color = "\033[1;32m" if not s.is_mirror else "\033[90m"
                mirror_flag = " \033[90m[mirror]\033[0m" if s.is_mirror else ""
                print(f" {s.session_id:<38}  {color}{tag:<10}\033[0m  {s.formatted_time:<16}  {s.turn_count:>5}  {s.clean_title}{mirror_flag}")

    elif args.subcommand == "sync":
        targets = [t.strip() for t in args.targets.split(",")] if args.targets else None

        if args.all:
            # Sync across all known workspace paths
            all_sessions = engine.list_sessions(folder_path=None, include_mirrors=False)
            unique_dirs = sorted(list(set(s.cwd for s in all_sessions if s.cwd and os.path.exists(s.cwd))))
            total_mirrored = 0
            if not args.quiet:
                print(f"Syncing across {len(unique_dirs)} workspaces...")
            for d in unique_dirs:
                res = syncer.sync_folder(d, target_agent_names=targets, dry_run=args.dry_run)
                total_mirrored += res["mirrored_created"]
            if not args.quiet:
                print(f"Sync complete. Created {total_mirrored} session mirrors across {len(unique_dirs)} workspaces.")
        else:
            folder = args.dir or os.getcwd()
            res = syncer.sync_folder(folder, target_agent_names=targets, dry_run=args.dry_run)
            if not args.quiet:
                print(f"\033[1;32mWorkspace:\033[0m {folder}")
                print(f"Scanned {res['scanned']} sessions ({res['originals']} originals).")
                print(f"Created/Updated {res['mirrored_created']} cross-agent mirrors.")
                if res["details"]:
                    for d in res["details"][:10]:
                        print(f"  ✓ {d}")
                    if len(res["details"]) > 10:
                        print(f"  ... and {len(res['details']) - 10} more.")

    elif args.subcommand == "resume":
        extra = args.extra_args if hasattr(args, "extra_args") else None
        sys.exit(engine.resume_session(args.session_id, target_agent_name=args.agent, extra_args=extra))

    elif args.subcommand == "preview":
        print(ui.render_preview(args.session_id))

    elif args.subcommand == "init":
        print(get_hook_script(args.shell))

    elif args.subcommand == "install-hooks":
        install_hooks()

    elif args.subcommand == "uninstall-hooks":
        uninstall_hooks()

    elif args.subcommand == "launch":
        handle_launch(args.agent, args.agent_args or [])

    elif args.subcommand == "info":
        installed = get_installed_adapters()
        all_ad = get_all_adapters()
        print("\033[1;36m=== AGENT SESSION HUB STATUS ===\033[0m\n")
        print(f"Total adapters available: {len(all_ad)}")
        print(f"Installed & active:       {len(installed)}\n")
        for a in all_ad:
            is_inst = a.is_installed()
            status = "\033[1;32m[INSTALLED]\033[0m" if is_inst else "\033[90m[NOT FOUND]\033[0m"
            count = len(a.scan_sessions()) if is_inst else 0
            bin_path = a.get_binary_path() or "N/A"
            print(f" • \033[1;37m{a.display_name:<20}\033[0m ({a.name:<8}) {status} - {count:>4} sessions found (CLI: {bin_path})")

if __name__ == "__main__":
    main()
