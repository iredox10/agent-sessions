import os
import sys
import shutil
import subprocess
from typing import List, Optional
from asess.models import UnifiedSession
from asess.engine import SessionEngine
from asess.adapters import get_adapter

class InteractiveUI:
    def __init__(self, engine: SessionEngine):
        self.engine = engine

    def render_preview(self, session_id: str) -> str:
        if session_id.strip() == "__NEW__":
            return (
                "\033[1;36m" + "━" * 60 + "\033[0m\n"
                "\033[1;32m✨ Start a New Session\033[0m\n\n"
                "• Press \033[1mENTER\033[0m to begin a brand new session in this workspace.\n"
                "• Or press \033[1mn\033[0m or \033[1mESC\033[0m to cancel and start fresh.\n"
                "• Select any session below to resume past context.\n"
                "\033[1;36m" + "━" * 60 + "\033[0m"
            )

        match = self.engine.find_session(session_id)
        if not match:
            return f"Session '{session_id}' not found."

        session, adapter = match
        turns = adapter.load_turns(session)

        lines = [
            "\033[1;36m" + "━" * 60 + "\033[0m",
            f"\033[1;37mSession ID:\033[0m     {session.session_id}",
            f"\033[1;37mOrigin Agent:\033[0m   \033[1;32m{adapter.display_name} ({session.origin_agent})\033[0m",
            f"\033[1;37mWorkspace:\033[0m      \033[33m{session.cwd}\033[0m",
            f"\033[1;37mLast Active:\033[0m    {session.formatted_time} ({session.relative_time})",
            f"\033[1;37mTotal Turns:\033[0m    {len(turns) or session.turn_count}",
            f"\033[1;37mTitle:\033[0m          \033[1m{session.title}\033[0m",
            "\033[1;36m" + "━" * 60 + "\033[0m",
            ""
        ]

        if not turns:
            lines.append("\033[90m(No transcript messages available for preview)\033[0m")
        else:
            lines.append("\033[1;34m=== CONVERSATION TRANSCRIPT ===\033[0m\n")
            for idx, turn in enumerate(turns):
                prefix = "\033[1;35m[User]\033[0m" if turn.role == "user" else "\033[1;32m[Agent]\033[0m"
                text = turn.text.strip()
                if len(text) > 800:
                    text = text[:797] + "..."
                lines.append(f"{prefix} \033[90m(turn {idx + 1})\033[0m:")
                for l in text.splitlines():
                    lines.append(f"  {l}")
                lines.append("")

        return "\n".join(lines)

    def run_fzf(self, folder_path: Optional[str] = None, all_workspaces: bool = False) -> Optional[UnifiedSession]:
        fzf_bin = shutil.which("fzf")
        if not fzf_bin:
            return self.run_curses(folder_path, all_workspaces)

        target_folder = None if all_workspaces else (folder_path or os.getcwd())
        sessions = self.engine.list_sessions(target_folder)

        if not sessions:
            if target_folder:
                print(f"No sessions found for {target_folder}. Try 'asess --all' to see all sessions.")
            else:
                print("No sessions found across any agent.")
            return None

        # Prepare lines for fzf
        # Format: <id> │ [<agent>] │ <date> │ <title> │ <turns>
        fzf_lines = []
        for s in sessions:
            tag = f"[{s.origin_agent}]"
            mirror_tag = " (mirror)" if s.is_mirror else ""
            line = f"{s.session_id:<45} │ {tag:<10} │ {s.formatted_time:<16} │ {s.turn_count:>3} turns │ {s.clean_title}{mirror_tag}"
            fzf_lines.append(line)

        input_data = "\n".join(fzf_lines).encode("utf-8")

        prompt_str = f"Agent Sessions [{target_folder or 'ALL'}] > "
        header_str = (
            "ENTER: Resume Native | "
            "a: agy | o: opencode | p: pi | c: cline | b: cbc | m: cmd | g: copilot"
        )

        preview_script = f"asess preview {{1}}"

        fzf_cmd = [
            fzf_bin,
            "--ansi",
            "--reverse",
            "--no-sort",
            "--prompt", prompt_str,
            "--header", header_str,
            "--preview", preview_script,
            "--preview-window", "right:55%:wrap",
            "--delimiter", "│",
            "--with-nth", "2..",
            "--expect", "ctrl-a,ctrl-o,ctrl-p,ctrl-c,ctrl-b,ctrl-m,ctrl-g"
        ]

        try:
            proc = subprocess.Popen(
                fzf_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None
            )
            out, _ = proc.communicate(input=input_data)
            if proc.returncode != 0 or not out:
                return None

            out_lines = out.decode("utf-8").strip().splitlines()
            if not out_lines:
                return None

            key_pressed = ""
            selected_line = ""
            if len(out_lines) == 2:
                key_pressed = out_lines[0]
                selected_line = out_lines[1]
            elif len(out_lines) == 1:
                selected_line = out_lines[0]

            sid = selected_line.split("│")[0].strip()
            match = self.engine.find_session(sid)
            if not match:
                return None

            session, _ = match

            # Check if custom key was pressed
            target_agent = None
            if key_pressed == "ctrl-a":
                target_agent = "agy"
            elif key_pressed == "ctrl-o":
                target_agent = "opencode"
            elif key_pressed == "ctrl-p":
                target_agent = "pi"
            elif key_pressed == "ctrl-c":
                target_agent = "cline"
            elif key_pressed == "ctrl-b":
                target_agent = "cbc"
            elif key_pressed == "ctrl-m":
                target_agent = "cmd"
            elif key_pressed == "ctrl-g":
                target_agent = "copilot"

            self.engine.resume_session(session.session_id, target_agent)
            return session
        except Exception as e:
            return None

    def run_curses(self, folder_path: Optional[str] = None, all_workspaces: bool = False) -> Optional[UnifiedSession]:
        """Simple fallback curses interface if fzf is missing."""
        import curses

        target_folder = None if all_workspaces else (folder_path or os.getcwd())
        sessions = self.engine.list_sessions(target_folder)
        if not sessions:
            print("No sessions found.")
            return None

        selected_idx = [0]
        selected_session = [None]
        target_agent_choice = [None]

        def draw(stdscr):
            curses.curs_set(0)
            stdscr.clear()

            while True:
                h, w = stdscr.getmaxyx()
                stdscr.clear()

                title_bar = f" AGENT SESSION HUB - {target_folder or 'ALL WORKSPACES'} "
                stdscr.addstr(0, 0, title_bar[:w], curses.A_REVERSE)

                instructions = " [↑/↓] Navigate  [Enter] Resume  [a]gy [o]pencode [p]i [c]line [b]cbc [m]cmd [q]uit "
                stdscr.addstr(h - 1, 0, instructions[:w], curses.A_DIM)

                max_items = h - 3
                idx = selected_idx[0]
                start_idx = max(0, idx - max_items // 2)
                end_idx = min(len(sessions), start_idx + max_items)

                for row, i in enumerate(range(start_idx, end_idx)):
                    s = sessions[i]
                    line_str = f" [{s.origin_agent:<8}] {s.formatted_time} ({s.turn_count:>2} turns) {s.clean_title}"
                    if i == idx:
                        stdscr.addstr(row + 1, 0, line_str[:w - 1], curses.A_STANDOUT)
                    else:
                        stdscr.addstr(row + 1, 0, line_str[:w - 1])

                key = stdscr.getch()
                if key in (curses.KEY_UP, ord('k')):
                    selected_idx[0] = max(0, selected_idx[0] - 1)
                elif key in (curses.KEY_DOWN, ord('j')):
                    selected_idx[0] = min(len(sessions) - 1, selected_idx[0] + 1)
                elif key in (10, 13):  # Enter
                    selected_session[0] = sessions[selected_idx[0]]
                    break
                elif key in (ord('a'), ord('A')):
                    selected_session[0] = sessions[selected_idx[0]]
                    target_agent_choice[0] = "agy"
                    break
                elif key in (ord('o'), ord('O')):
                    selected_session[0] = sessions[selected_idx[0]]
                    target_agent_choice[0] = "opencode"
                    break
                elif key in (ord('p'), ord('P')):
                    selected_session[0] = sessions[selected_idx[0]]
                    target_agent_choice[0] = "pi"
                    break
                elif key in (ord('c'), ord('C')):
                    selected_session[0] = sessions[selected_idx[0]]
                    target_agent_choice[0] = "cline"
                    break
                elif key in (ord('b'), ord('B')):
                    selected_session[0] = sessions[selected_idx[0]]
                    target_agent_choice[0] = "cbc"
                    break
                elif key in (ord('m'), ord('M')):
                    selected_session[0] = sessions[selected_idx[0]]
                    target_agent_choice[0] = "cmd"
                    break
                elif key in (ord('q'), 27):  # q or ESC
                    break

        curses.wrapper(draw)

        if selected_session[0]:
            self.engine.resume_session(selected_session[0].session_id, target_agent_choice[0])
            return selected_session[0]
        return None

    def run_agent_launch_picker(self, agent_name: str, sessions: List[UnifiedSession]) -> Optional[UnifiedSession]:
        """
        Interactive launcher picker when an agent (e.g. pi, cmd, cbc, cline) is opened in a folder.
        Returns selected UnifiedSession to resume, or None to start a new session.
        """
        if not sys.stdin.isatty():
            return None

        fzf_bin = shutil.which("fzf")
        adapter = get_adapter(agent_name)
        display_name = adapter.display_name if adapter else agent_name.capitalize()
        folder_name = os.path.basename(os.getcwd()) or os.getcwd()

        if fzf_bin:
            # Build fzf items: first item is New Session
            fzf_lines = [
                f"__NEW__ │ \033[1;32m[+ NEW]\033[0m    │ {'Just now':<16} │   - turns │ \033[1;32m✨ Start a new session in {display_name}\033[0m"
            ]
            for s in sessions:
                tag = f"[{s.origin_agent}]"
                color = "\033[1;36m"
                line = f"{s.session_id:<45} │ {color}{tag:<10}\033[0m │ {s.formatted_time:<16} │ {s.turn_count:>3} turns │ {s.clean_title}"
                fzf_lines.append(line)

            input_data = "\n".join(fzf_lines).encode("utf-8")
            prompt_str = f"{display_name} [{folder_name}] > "
            header_str = "ENTER: Open selected session | 'n' / ESC: Start new session"
            preview_script = "asess preview {1}"

            fzf_cmd = [
                fzf_bin,
                "--ansi",
                "--reverse",
                "--no-sort",
                "--prompt", prompt_str,
                "--header", header_str,
                "--preview", preview_script,
                "--preview-window", "right:55%:wrap",
                "--delimiter", "│",
                "--with-nth", "2..",
                "--expect", "n,ctrl-n,esc"
            ]

            try:
                proc = subprocess.Popen(
                    fzf_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=None
                )
                out, _ = proc.communicate(input=input_data)
                if proc.returncode != 0 or not out:
                    return None

                out_lines = out.decode("utf-8").strip().splitlines()
                if not out_lines:
                    return None

                key_pressed = ""
                selected_line = ""
                if len(out_lines) == 2:
                    key_pressed = out_lines[0]
                    selected_line = out_lines[1]
                elif len(out_lines) == 1:
                    selected_line = out_lines[0]

                if key_pressed in ("n", "ctrl-n", "esc"):
                    return None

                sid = selected_line.split("│")[0].strip()
                if sid == "__NEW__":
                    return None

                match = self.engine.find_session(sid)
                if match:
                    return match[0]
            except Exception:
                pass
            return None

        # Fallback simple CLI menu
        print(f"\n\033[1;36m══════════════════════════════════════════════════════════════════════════════\033[0m")
        print(f"  \033[1m{display_name}\033[0m — Past sessions found in \033[33m{os.getcwd()}\033[0m:")
        print(f"\033[1;36m══════════════════════════════════════════════════════════════════════════════\033[0m")
        print(f"  [0] \033[1;32m✨ Start a new session in {display_name}\033[0m")
        for idx, s in enumerate(sessions[:15], 1):
            print(f"  [{idx}] \033[1;34m[{s.origin_agent}]\033[0m {s.formatted_time} ({s.turn_count} turns) - {s.clean_title}")
        print(f"\033[1;36m──────────────────────────────────────────────────────────────────────────────\033[0m")

        try:
            choice = input(f"Select a session [0-{min(len(sessions), 15)}] or 'n' for new (default: 0): ").strip()
            if not choice or choice.lower() in ("0", "n", "new"):
                return None
            num = int(choice)
            if 1 <= num <= len(sessions):
                return sessions[num - 1]
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        return None
