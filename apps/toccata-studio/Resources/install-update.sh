#!/bin/sh
# Runs only after Studio has saved tasks and stopped its collection helper.
# All paths are positional arguments, never interpolated into shell source.
set -eu
umask 077
[ "$#" -eq 7 ] || [ "$#" -eq 9 ] || exit 1
parent_pid=$1
target=$2
staged=$3
backup=$4
work=$5
identity=$6
version=$7
channel=${8:-upstream}
staged_hash=${9:-}
case "$parent_pid" in ''|*[!0-9]*) exit 1 ;; esac
[ "$parent_pid" -gt 1 ] || exit 1
case "$target" in /*.app) ;; *) exit 1 ;; esac
parent=${target%/*}
case "$staged" in "$parent"/.Toccata-update-*.app) ;; *) exit 1 ;; esac
case "$backup" in "$parent"/.Toccata-backup-*.app) ;; *) exit 1 ;; esac
[ -d "$work" ] && [ ! -L "$work" ] || exit 1
[ ! -e "$backup" ] && [ ! -L "$backup" ] || exit 1

case "$channel:$#" in
    upstream:7) bundle_id=com.toccata.studio ;;
    personal:9)
        bundle_id=cn.ericgao.toccata.personal
        [ "$target" = "$parent/Toccata Personal.app" ] || exit 1
        [ "${staged%/*}" = "$parent" ] && [ "${backup%/*}" = "$parent" ] || exit 1
        case "$staged_hash" in ''|*[!0-9a-f]*) exit 1 ;; esac
        [ "${#staged_hash}" -eq 40 ] || exit 1
        ;;
    *) exit 1 ;;
esac

app_value() {
    /usr/libexec/PlistBuddy -c "Print :$2" "$1/Contents/Info.plist"
}

validate() {
    [ -d "$target" ] && [ ! -L "$target" ] && [ -d "$staged" ] && [ ! -L "$staged" ] || return 1
    [ ! -e "$backup" ] && [ ! -L "$backup" ] || return 1
    [ "$(/usr/bin/stat -f '%d:%i' "$target")" = "$identity" ] || return 1
    [ "$(app_value "$staged" CFBundleIdentifier)" = "$bundle_id" ] || return 1
    [ "$(app_value "$staged" CFBundleShortVersionString)" = "$version" ] || return 1
    /usr/bin/codesign --verify --deep --strict "$staged" || return 1
    if [ "$channel" = personal ]; then
        [ "$(app_value "$target" CFBundleIdentifier)" = "$bundle_id" ] || return 1
        for app in "$target" "$staged"; do
            [ "$(app_value "$app" CFBundleExecutable)" = ToccataPersonal ] || return 1
            [ "$(app_value "$app" ToccataDistributionChannel)" = personal-stable ] || return 1
            [ "$(app_value "$app" ToccataUpdateMode)" = in-app ] || return 1
        done
        code_info=$(/usr/bin/codesign -d --verbose=4 "$staged" 2>&1) || return 1
        [ "$(printf '%s\n' "$code_info" | /usr/bin/sed -n 's/^CDHash=//p')" = "$staged_hash" ] || return 1
    fi
    return 0
}
validate
: > "$work/ready"
attempts=0
while kill -0 "$parent_pid" 2>/dev/null; do
    attempts=$((attempts + 1))
    [ "$attempts" -le 1200 ] || exit 1
    /bin/sleep 0.1
done

old_moved=0
new_installed=0
recover() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$code" -ne 0 ]; then
        if [ "$old_moved" -eq 1 ]; then
            if [ "$new_installed" -eq 1 ]; then /bin/mv "$target" "$staged" || exit 1; fi
            /bin/mv "$backup" "$target" || exit 1
        fi
        # Keep diagnostics and staged files on failure; never delete the old app.
        if [ ! -L "$target" ] && [ "$(/usr/bin/stat -f '%d:%i' "$target" 2>/dev/null)" = "$identity" ]; then
            /usr/bin/open -n "$target" --args --update-failed || true
        fi
    fi
    exit "$code"
}
trap recover EXIT
trap 'exit 1' HUP INT TERM
validate
/bin/mv "$target" "$backup"
old_moved=1
/bin/mv "$staged" "$target"
new_installed=1
/usr/bin/open -n "$target" --args --toccata-updated "$work"
# Keep the previous app until a later successful launch cleans it up. The
# backup is intentionally recoverable if Launch Services accepts a bad launch.
trap - EXIT HUP INT TERM
exit 0
