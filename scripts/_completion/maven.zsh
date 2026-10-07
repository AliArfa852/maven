#compdef maven maven-backup maven-calendar maven-contacts maven-cookbook maven-docs maven-gallery maven-logs maven-mail maven-mcp maven-memory maven-notes maven-personal maven-preset maven-research maven-sessions maven-signature maven-skills maven-tasks maven-theme maven-users maven-webhook
# Zsh tab-completion for the maven umbrella + sub-CLIs.
#
# Drop in any directory on $fpath, e.g.:
#     fpath=(/path/to/maven/scripts/_completion $fpath)
#     autoload -U compinit; compinit
#
# Then `maven <tab>` completes subcommands; `maven mail <tab>`
# completes mail subcommands; `maven-mail <tab>` works the same.

_maven_scripts_dir() {
    local self="${(%):-%x}"
    while [[ -L "$self" ]]; do self="$(readlink "$self")"; done
    cd "${self:h}/.." && pwd
}

typeset -gA _maven_subs

_maven_refresh() {
    _maven_subs=()
    local dir="$(_maven_scripts_dir)"
    local py="$dir/../venv/bin/python"
    [[ -x "$py" ]] || py="$(command -v python3)"
    local f sub help_out commands
    for f in "$dir"/maven-*; do
        [[ -x "$f" ]] || continue
        case "$f" in
            *.bak|*.pyc|*.pre-*) continue ;;
        esac
        sub="${${f:t}#maven-}"
        help_out=$("$py" "$f" --help 2>/dev/null) || continue
        commands=$(echo "$help_out" | grep -oE '\{[a-z0-9_,-]+\}' | head -1 \
            | tr -d '{}' | tr ',' ' ')
        _maven_subs[$sub]="$commands"
    done
}

_maven() {
    [[ ${#_maven_subs} -eq 0 ]] && _maven_refresh

    local cmd="${words[1]}"

    if [[ "$cmd" == "maven" ]]; then
        if (( CURRENT == 2 )); then
            local -a subs=(${(k)_maven_subs} help)
            _describe 'subcommand' subs
            return
        fi
        local sub="${words[2]}"
        if [[ "$sub" == "help" ]] && (( CURRENT == 3 )); then
            local -a subs=(${(k)_maven_subs})
            _describe 'subcommand' subs
            return
        fi
        if (( CURRENT == 3 )); then
            local -a sc=(${(s/ /)_maven_subs[$sub]})
            _describe 'command' sc
            return
        fi
        return
    fi

    # maven-foo <tab>
    local sub="${cmd#maven-}"
    if (( CURRENT == 2 )); then
        local -a sc=(${(s/ /)_maven_subs[$sub]})
        _describe 'command' sc
        return
    fi
}

_maven "$@"
