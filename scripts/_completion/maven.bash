#!/usr/bin/env bash
# Tab-completion for the `maven` umbrella + every `maven-*` CLI.
#
# Source from your shell rc:
#     source /path/to/maven/scripts/_completion/maven.bash
#
# Or wire it once per machine:
#     sudo install -m 644 maven.bash /etc/bash_completion.d/maven
#
# What it does:
#   - On the first word after `maven`, complete with the list of
#     subcommands (`mail`, `calendar`, ...).
#   - On subsequent words, complete with the subcommand's first-token
#     subcommands (`list`, `show`, ...) which we cache by parsing the
#     tool's own --help output. Updates lazily; refresh by running
#     `_maven_refresh_cache`.
#   - Same completion works for the individual `maven-foo` scripts.

_maven_scripts_dir() {
    # Resolve the scripts/ dir from the script that sources us. We assume
    # the user sourced the file directly out of scripts/_completion/.
    local self="${BASH_SOURCE[0]}"
    while [ -L "$self" ]; do self=$(readlink "$self"); done
    cd "$(dirname "$self")/.." && pwd
}

declare -A _MAVEN_SUBS_CACHE=()

_maven_refresh_cache() {
    local dir="$(_maven_scripts_dir)"
    _MAVEN_SUBS_CACHE=()
    # Prefer the project venv's Python so deps (bcrypt, sqlalchemy, ...)
    # resolve. Falls back to system `python3` for container installs.
    local py="$dir/../venv/bin/python"
    [ -x "$py" ] || py="$(command -v python3)"
    local f
    for f in "$dir"/maven-*; do
        [ -x "$f" ] || continue
        case "$f" in *.bak|*.pyc|*.pre-*) continue ;; esac
        local name="$(basename "$f")"
        local sub="${name#maven-}"
        local help_out
        help_out=$("$py" "$f" --help 2>/dev/null) || continue
        local commands
        commands=$(echo "$help_out" | grep -oE '\{[a-z0-9_,-]+\}' | head -1 \
            | tr -d '{}' | tr ',' ' ')
        _MAVEN_SUBS_CACHE[$sub]="$commands"
    done
}

_maven_complete() {
    [ ${#_MAVEN_SUBS_CACHE[@]} -eq 0 ] && _maven_refresh_cache

    local cur="${COMP_WORDS[COMP_CWORD]}"
    local cmd="${COMP_WORDS[0]}"

    # `maven <tab>` → list every subcommand
    if [ "$cmd" = "maven" ]; then
        if [ "$COMP_CWORD" -eq 1 ]; then
            local subs="${!_MAVEN_SUBS_CACHE[@]} help"
            COMPREPLY=($(compgen -W "$subs" -- "$cur"))
            return 0
        fi
        # `maven foo <tab>` — complete with foo's own subcommands
        local sub="${COMP_WORDS[1]}"
        # `maven help <tab>` lists every subcommand
        if [ "$sub" = "help" ] && [ "$COMP_CWORD" -eq 2 ]; then
            COMPREPLY=($(compgen -W "${!_MAVEN_SUBS_CACHE[*]}" -- "$cur"))
            return 0
        fi
        if [ "$COMP_CWORD" -eq 2 ]; then
            COMPREPLY=($(compgen -W "${_MAVEN_SUBS_CACHE[$sub]}" -- "$cur"))
            return 0
        fi
        return 0
    fi

    # Direct `maven-foo <tab>` (no umbrella)
    local sub="${cmd#maven-}"
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=($(compgen -W "${_MAVEN_SUBS_CACHE[$sub]}" -- "$cur"))
        return 0
    fi
}

# Register the completion for every maven-* script + the umbrella.
complete -F _maven_complete maven
for f in "$(_maven_scripts_dir)"/maven-*; do
    [ -x "$f" ] || continue
    case "$f" in *.bak|*.pyc|*.pre-*) continue ;; esac
    complete -F _maven_complete "$(basename "$f")"
done
