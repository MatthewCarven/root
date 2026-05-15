# root shell function for bash / zsh.
#
# Install (one-shot, in your ~/.bashrc or ~/.zshrc):
#     eval "$(root init-shell bash)"          # or  zsh
#
# After running `root` with no args, the function captures the chosen path
# from `root which` and cds into it. If the user cancels, nothing changes.
# `command root` is used so this function doesn't recursively call itself.

root() {
    if [ "$#" -gt 0 ]; then
        command root "$@"
        return $?
    fi

    command root
    local _rc=$?
    if [ $_rc -ne 0 ]; then
        return $_rc
    fi

    local _target
    _target="$(command root which 2>/dev/null)"
    if [ -n "$_target" ] && [ -d "$_target" ]; then
        cd -- "$_target" || return $?
    fi
}
