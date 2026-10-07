# AgentSessionHub (`asess` / `agent-sessions`)

<p align="center">
  <img src="https://raw.githubusercontent.com/iredox10/agent-sessions/main/assets/banner.png" alt="AgentSessionHub Banner" width="600" onerror="this.style.display='none'"/>
</p>

<p align="center">
  <a href="https://github.com/iredox10/agent-sessions/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/iredox10/agent-sessions/ci.yml?branch=main&label=CI&style=flat-square" alt="CI Status"></a>
  <a href="https://pypi.org/project/agent-sessions/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg?style=flat-square" alt="Python 3.9+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License: MIT"></a>
  <a href="https://github.com/iredox10/agent-sessions/issues"><img src="https://img.shields.io/github/issues/iredox10/agent-sessions?style=flat-square" alt="Open Issues"></a>
  <a href="https://github.com/iredox10/agent-sessions/stargazers"><img src="https://img.shields.io/github/stars/iredox10/agent-sessions?style=flat-square" alt="GitHub Stars"></a>
</p>

<h3 align="center">
  Universal Cross-Agent Session Management & Resuming Engine for AI Coding Agents
</h3>

<p align="center">
  <b>Pick up exactly where you left off — in any project folder, with any coding agent.</b>
</p>

---

## 💡 The Problem

Modern AI developers don't use just one coding agent. You might use **Antigravity (AGY)** for architectural planning, **OpenCode** or **Pi** for fast terminal editing, **Cline** for complex autonomous coding, or **GitHub Copilot CLI** for quick checks.

However, each agent stores its sessions in its own proprietary silo:
- SQLite databases in `~/.local/share/opencode` or `~/.cline/data`
- Slug-encoded JSONL directories in `~/.pi/agent/sessions/--path--/`
- Transcripts tucked inside tool-specific cache directories

When you return to a project directory weeks later, **none of the agents know what you discussed in the others**. You have to remember which agent you used, search separate histories, or re-explain context from scratch.

---

## ✨ The Solution: `AgentSessionHub`

**`AgentSessionHub` (`asess`)** breaks down agent silos and unifies session history across all your coding tools:

1. **Folder-Aware Session Picker**: Open *any* agent (`pi`, `opencode`, `agy`, `cline`, `cbc`, `cmd`, etc.) in *any* workspace, and it presents all past conversations started in that directory across **all** tools.
2. **Fresh Session Support**: Option `[0] ✨ Start a new session` is always front and center. Empty folders launch clean sessions immediately with zero prompts.
3. **Zero-Latency Pass-Through**: Passing flags or prompts (e.g. `pi --version`, `cmd -v`, `pi "fix bug"`) bypasses the selector and executes the real agent binary instantly.
4. **Rich Interactive Preview**: Powered by `fzf` with full scrollable conversation transcript preview (turns, timestamps, user prompts, agent replies).
5. **Cross-Agent Resuming & Bridging**: Start a task with OpenCode, resume it in Pi Agent. Start with Antigravity, continue with Cline. Format conversions happen on-the-fly.

```
                      ┌────────────────────────────────────────┐
                      │  You type: pi (or cmd, opencode, etc.) │
                      └──────────────────┬─────────────────────┘
                                         ▼
                     ┌───────────────────────────────────────┐
                     │ Sessions started in this folder?      │
                     └───────┬───────────────────────┬───────┘
                             │ YES                   │ NO
                             ▼                       ▼
            ┌──────────────────────────────────┐  ┌─────────────────────┐
            │ Interactive Session Picker:      │  │ Starts fresh        │
            │  [0] ✨ Start a new session      │  │ session immediately │
            │  [1] [opencode] Fix navbar...    │  └─────────────────────┘
            │  [2] [cline] Add auth api...     │
            │  [3] [agy] Database migration... │
            │ (with conversation preview pane) │
            └────────────────┬─────────────────┘
                             │
            ┌────────────────┴──────────────────┐
            ▼                                   ▼
    [+ Start a new session]             [Select any past session]
    Starts fresh agent session          Resumes past context (bridges
                                        automatically if cross-agent)
```

---

## ⚡ Quickstart & Installation

### Option 1: One-Line Installer (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/iredox10/agent-sessions/main/install.sh | bash
```

The installer detects your shell (`zsh`, `bash`, `fish`), sets up transparent shell hooks, and configures the `asess` CLI.

### Option 2: Using `pipx` or `pip`

```bash
# Using pipx (recommended for standalone CLI tools)
pipx install git+https://github.com/iredox10/agent-sessions.git

# Or standard pip
pip install --user git+https://github.com/iredox10/agent-sessions.git

# Install shell hooks
asess install-hooks
```

### Option 3: From Source

```bash
git clone https://github.com/iredox10/agent-sessions.git
cd agent-sessions
pip install -e .
asess install-hooks
```

*(Optional but recommended)*: Install [`fzf`](https://github.com/junegunn/fzf) for fuzzy searching and side-by-side transcript previews:
```bash
# macOS
brew install fzf

# Ubuntu / Debian
sudo apt install fzf

# Fedora
sudo dnf install fzf
```

---

## 🤖 Supported Coding Agents (11 Harnesses)

`AgentSessionHub` automatically discovers, extracts, formats, and mirrors conversations across all 11 major AI coding agent harnesses:

| Agent Harness | CLI Command | Session Store Location | Native Resume Syntax |
| :--- | :---: | :--- | :--- |
| **Antigravity** | `agy` | `~/.gemini/antigravity-cli/` | `agy --conversation <id>` |
| **OpenCode** | `opencode` | `~/.local/share/opencode/opencode.db` | `opencode -s <id>` |
| **Pi Coding Agent** | `pi` | `~/.pi/agent/sessions/--<slug>--/` | `pi --session <path\|id>` |
| **Cline CLI** | `cline` | `~/.cline/data/` | `cline --id <id>` |
| **CodeBuddy Code** | `cbc` | `~/.codebuddy/projects/<slug>/` | `cbc -r <id>` |
| **Command Code** | `cmd` | `~/.commandcode/projects/<slug>/` | `cmd --session <id>` |
| **GitHub Copilot** | `copilot` | `~/.copilot/session-store.db` | `copilot sessions resume <id>` |
| **OpenAI Codex** | `codex` | `~/.codex/sessions/` | `codex --session <id>` |
| **Qwen Code** | `qwen` | `~/.qwen/projects/<slug>/chats/` | `qwen --resume <id>` |
| **Grok** | `grok` | `~/.grok/sessions/<url-encoded-dir>/` | `grok resume <id>` |
| **Adal** | `adal` | `~/.adal/sessions/` | `adal resume <id>` |

---

## 🛠️ CLI Usage

```bash
# 1. Interactive session browser in the current directory
asess

# 2. Global session browser across ALL workspaces on your computer
asess --all

# 3. List sessions in current folder (clean tabular output)
asess list

# 4. List original sessions only (exclude mirrored copies)
asess list --no-mirrors

# 5. Preview the full conversation transcript of any session
asess preview <session-id>

# 6. Resume a session in its native agent or any other harness
asess resume <session-id>
asess resume <session-id> --agent pi
asess resume <session-id> --agent opencode

# 7. Synchronize sessions across all agents in the workspace
asess sync

# 8. Check system diagnostics, installed agents, and session counts
asess info

# 9. Shell hooks management
asess install-hooks
asess uninstall-hooks
```

---

## 🔄 Cross-Agent Resuming & Bridging

Ever started a complex architectural debugging session in Antigravity or OpenCode, and wanted to continue it using Pi Agent or Cline?

```bash
# Resume an OpenCode session inside Pi Agent
asess resume opencode:ses_f2d15ec48ffe --agent pi

# Resume an Antigravity conversation inside Cline
asess resume agy:444ed637-a6f0-4af9-b158 --agent cline

# Resume a Cline session inside CodeBuddy Code
asess resume cline:1790951959364_vhvjg --agent cbc
```

`asess` extracts the conversation turns (user requests, model responses, timestamps) from the origin agent, formats them into the target agent's native storage representation, and boots the target agent directly into the resumed state.

---

## ⚙️ Configuration & Customization

Custom binary locations and preferences can be defined in `~/.config/asess/config.json`:

```json
{
  "binaries": {
    "pi": "/custom/path/to/pi",
    "opencode": "/usr/local/bin/opencode"
  },
  "fzf_preview": true,
  "default_agent": "pi"
}
```

Or overridden using environment variables:
```bash
export ASESS_PI_BIN="/custom/bin/pi"
export ASESS_OPENCODE_BIN="/custom/bin/opencode"
```

---

## 🧪 Testing

Run the automated unit test suite with:

```bash
python3 -m unittest discover tests
```

---

## 🤝 Contributing

We welcome contributions! Whether adding support for a new AI coding agent, fixing a bug, or improving documentation, check out our [Contributing Guide](CONTRIBUTING.md).

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright &copy; 2026 iredox.
