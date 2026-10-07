#!/usr/bin/env bash
# ==============================================================================
# AgentSessionHub (asess) — One-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/iredox10/agent-sessions/main/install.sh | bash
# ==============================================================================

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[1;32m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
cat << 'EOF'
     ___                    _     ____                _                 
    / _ \__ _  ___ _ __  __| |_  / ___|  ___  ___ ___(_) ___  _ __  ___ 
   / /_\ / _` |/ _ \ '_ \/ _` (_) \___ \ / _ \/ __/ __| |/ _ \| '_ \/ __|
  / /_\\  (_| |  __/ | | | (_| |_   ___) |  __/\__ \__ \ | (_) | | | \__ \
  \____/ \__, |\___|_| |_|\__,_(_) |____/ \___||___/___/_|\___/|_| |_|___/
         |___/                                                            
EOF
echo -e "${RESET}"
echo -e "${BOLD}Universal Cross-Agent Session Management & Resuming Engine${RESET}"
echo -e "${CYAN}------------------------------------------------------------------${RESET}\n"

# 1. Check Python version
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}Error: python3 is required but was not found in PATH.${RESET}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo -e "${RED}Error: Python 3.9 or higher is required (found Python ${PYTHON_VERSION}).${RESET}"
    exit 1
fi

echo -e "  ${GREEN}✓${RESET} Detected Python ${PYTHON_VERSION}"

# 2. Setup install directory
INSTALL_DIR="$HOME/.local/share/agent-sessions"
REPO_URL="${ASESS_REPO_URL:-https://github.com/iredox10/agent-sessions.git}"

echo -e "  ${GREEN}✓${RESET} Installing into ${CYAN}${INSTALL_DIR}${RESET}..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "  ${CYAN}•${RESET} Updating existing installation..."
    git -C "$INSTALL_DIR" pull --quiet origin main || true
elif [ -d "$INSTALL_DIR" ]; then
    echo -e "  ${CYAN}•${RESET} Directory exists, pulling latest..."
    git -C "$INSTALL_DIR" pull --quiet || true
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    if command -v git >/dev/null 2>&1; then
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    else
        echo -e "${RED}Error: git is required to clone the repository.${RESET}"
        exit 1
    fi
fi

# 3. Install executable
mkdir -p "$HOME/.local/bin"
BIN_LINK="$HOME/.local/bin/asess"

cat << EOF > "$BIN_LINK"
#!/usr/bin/env python3
import sys, os
pkg_dir = "$INSTALL_DIR"
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)
from asess.cli import main
if __name__ == "__main__":
    main()
EOF
chmod +x "$BIN_LINK"
ln -sf "$BIN_LINK" "$HOME/.local/bin/agent-sessions"

echo -e "  ${GREEN}✓${RESET} CLI binary linked at ${CYAN}$HOME/.local/bin/asess${RESET}"

# 4. Check fzf for rich interactive UI
if command -v fzf >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} fzf fuzzy finder detected (full preview pane active)"
else
    echo -e "  ${YELLOW}!${RESET} fzf not found. Falling back to curses/terminal menu."
    echo -e "    ${BOLD}Tip:${RESET} Install fzf ('sudo apt install fzf' / 'brew install fzf') for rich transcript previews."
fi

# 5. Install transparent shell hooks
echo -e "  ${CYAN}•${RESET} Installing shell hooks for workspace session awareness..."
"$BIN_LINK" install-hooks >/dev/null 2>&1 || true
echo -e "  ${GREEN}✓${RESET} Shell hooks configured for zsh, bash, and fish"

# 6. Ensure ~/.local/bin is in PATH
CURRENT_PATH=":$PATH:"
if [ "${CURRENT_PATH#*:$HOME/.local/bin:}" = "$CURRENT_PATH" ]; then
    echo -e "\n  ${YELLOW}! Note:${RESET} Please ensure ${BOLD}~/.local/bin${RESET} is in your PATH."
    echo -e "    Add to your shell profile: ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi

echo -e "\n${GREEN}${BOLD}Installation complete! 🎉${RESET}\n"
echo -e "To get started:"
echo -e "  1. Restart your terminal or reload your shell profile:"
echo -e "     ${CYAN}source ~/.zshrc${RESET} (or ${CYAN}source ~/.bashrc${RESET})"
echo -e "  2. Go into any project folder and launch your favorite agent:"
echo -e "     ${CYAN}pi${RESET} | ${CYAN}cmd${RESET} | ${CYAN}opencode${RESET} | ${CYAN}cline${RESET} | ${CYAN}agy${RESET} | ${CYAN}codex${RESET}"
echo -e "  3. Or run the session browser directly:"
echo -e "     ${CYAN}asess${RESET}               (browse sessions in current folder)"
echo -e "     ${CYAN}asess --all${RESET}         (browse sessions across all workspaces)"
echo -e "     ${CYAN}asess info${RESET}          (view installed agents & statistics)\n"
