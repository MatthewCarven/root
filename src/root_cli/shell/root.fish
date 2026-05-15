# root shell function for fish.
#
# Install:
#     root init-shell fish | source
# Or save it permanently:
#     root init-shell fish > ~/.config/fish/functions/root.fish

function root --description 'Jump to the folder you want, fast'
    if test (count $argv) -gt 0
        command root $argv
        return $status
    end

    command root
    set -l _rc $status
    if test $_rc -ne 0
        return $_rc
    end

    set -l _target (command root which 2>/dev/null)
    if test -n "$_target" -a -d "$_target"
        cd -- "$_target"
    end
end
