import os
import sys

ZSH_HOOK_TEMPLATE = """# >>> agent-sessions shell integration >>>
# Shows past sessions and synchronizes across all agents in the current folder

_asess_bg_sync() {
    (command asess sync --quiet --dir "$PWD" >/dev/null 2>&1 &)
}

autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook chpwd _asess_bg_sync

agy() {
    command asess launch agy "$@"
}

opencode() {
    command asess launch opencode "$@"
}

pi() {
    command asess launch pi "$@"
}

cline() {
    command asess launch cline "$@"
}

cbc() {
    command asess launch cbc "$@"
}

cmd() {
    command asess launch cmd "$@"
}

copilot() {
    command asess launch copilot "$@"
}

codex() {
    command asess launch codex "$@"
}

qwen() {
    command asess launch qwen "$@"
}

grok() {
    command asess launch grok "$@"
}

adal() {
    command asess launch adal "$@"
}

alias sessions='asess'
alias agent-sessions='asess'
# <<< agent-sessions shell integration <<<
"""

BASH_HOOK_TEMPLATE = """# >>> agent-sessions shell integration >>>
_asess_bg_sync() {
    (command asess sync --quiet --dir "$PWD" >/dev/null 2>&1 &)
}

agy() {
    command asess launch agy "$@"
}

opencode() {
    command asess launch opencode "$@"
}

pi() {
    command asess launch pi "$@"
}

cline() {
    command asess launch cline "$@"
}

cbc() {
    command asess launch cbc "$@"
}

cmd() {
    command asess launch cmd "$@"
}

copilot() {
    command asess launch copilot "$@"
}

codex() {
    command asess launch codex "$@"
}

qwen() {
    command asess launch qwen "$@"
}

grok() {
    command asess launch grok "$@"
}

adal() {
    command asess launch adal "$@"
}

alias sessions='asess'
alias agent-sessions='asess'
# <<< agent-sessions shell integration <<<
"""

FISH_HOOK_TEMPLATE = """# >>> agent-sessions shell integration >>>
# Shows past sessions and synchronizes across all agents in the current folder

function _asess_bg_sync --on-variable PWD
    command asess sync --quiet --dir "$PWD" >/dev/null 2>&1 &
end

function agy; command asess launch agy $argv; end
function opencode; command asess launch opencode $argv; end
function pi; command asess launch pi $argv; end
function cline; command asess launch cline $argv; end
function cbc; command asess launch cbc $argv; end
function cmd; command asess launch cmd $argv; end
function copilot; command asess launch copilot $argv; end
function codex; command asess launch codex $argv; end
function qwen; command asess launch qwen $argv; end
function grok; command asess launch grok $argv; end
function adal; command asess launch adal $argv; end

alias sessions asess
alias agent-sessions asess
# <<< agent-sessions shell integration <<<
"""

def get_hook_script(shell_name: str) -> str:
    shell = shell_name.lower()
    if "zsh" in shell:
        return ZSH_HOOK_TEMPLATE
    elif "fish" in shell:
        return FISH_HOOK_TEMPLATE
    return BASH_HOOK_TEMPLATE

def install_hooks() -> bool:
    home = os.path.expanduser("~")
    target_files = []
    zshrc = os.path.join(home, ".zshrc")
    bashrc = os.path.join(home, ".bashrc")
    fish_config = os.path.join(home, ".config", "fish", "config.fish")

    if os.path.exists(zshrc):
        target_files.append((zshrc, ZSH_HOOK_TEMPLATE))
    if os.path.exists(bashrc):
        target_files.append((bashrc, BASH_HOOK_TEMPLATE))
    if os.path.exists(fish_config):
        target_files.append((fish_config, FISH_HOOK_TEMPLATE))

    tag = "# >>> agent-sessions shell integration >>>"

    installed_any = False
    for fpath, template in target_files:
        try:
            content = ""
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as fp:
                    content = fp.read()

            if tag in content:
                # Already installed, replace existing block
                start = content.find(tag)
                end = content.find("# <<< agent-sessions shell integration <<<")
                if end != -1:
                    end += len("# <<< agent-sessions shell integration <<<")
                    new_content = content[:start].rstrip() + "\n\n" + template + "\n" + content[end:].lstrip()
                else:
                    new_content = content + "\n\n" + template + "\n"
            else:
                new_content = content.rstrip() + "\n\n" + template + "\n"

            with open(fpath, "w", encoding="utf-8") as fp:
                fp.write(new_content)
            print(f"Installed agent-sessions shell hooks into {fpath}")
            installed_any = True
        except Exception as e:
            print(f"Failed to install hooks to {fpath}: {e}", file=sys.stderr)

    return installed_any

def uninstall_hooks() -> bool:
    home = os.path.expanduser("~")
    target_files = [
        os.path.join(home, ".zshrc"),
        os.path.join(home, ".bashrc"),
        os.path.join(home, ".config", "fish", "config.fish")
    ]
    tag_start = "# >>> agent-sessions shell integration >>>"
    tag_end = "# <<< agent-sessions shell integration <<<"

    for fpath in target_files:
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as fp:
                content = fp.read()

            if tag_start in content:
                start = content.find(tag_start)
                end = content.find(tag_end)
                if end != -1:
                    end += len(tag_end)
                    new_content = content[:start].rstrip() + "\n" + content[end:].lstrip()
                    with open(fpath, "w", encoding="utf-8") as fp:
                        fp.write(new_content)
                    print(f"Removed shell hooks from {fpath}")
        except Exception as e:
            print(f"Error removing hooks from {fpath}: {e}", file=sys.stderr)

    return True
