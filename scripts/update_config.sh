#!/bin/sh
# OpenWrt/BusyBox ash compatible. Validate and update each service as a transaction.
set -u
umask 077
BASE_URL=${CONFIG_BASE_URL:-https://raw.githubusercontent.com/kxhubs/Actions-OpenWrt/main/other}
case "$BASE_URL" in https://*) ;; *) echo 'Only HTTPS configuration sources are supported' >&2; exit 1 ;; esac
[ "$(id -u)" = 0 ] || { echo 'Run on the router as root' >&2; exit 1; }
for tool in curl uci jsonfilter ubus; do
    command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
LOCK=/tmp/update-config.lock
mkdir "$LOCK" 2>/dev/null || { echo 'Another update is running, or a stale lock exists' >&2; exit 1; }
TEMP=$(mktemp -d) || { rmdir "$LOCK"; exit 1; }
cleanup() { rm -rf "$TEMP"; rmdir "$LOCK"; }
trap cleanup EXIT
interrupted() {
    trap - EXIT
    printf 'Update interrupted; backups retained at %s; inspect before retrying\n' "$TEMP" >&2
    rmdir "$LOCK"
    exit 1
}
trap interrupted HUP INT TERM
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
# YAML files require a real parser; never substitute a nonempty-file check.
validate() {
    case "$1" in
        *.yaml)
            command -v ruby >/dev/null || { log 'YAML validation requires Ruby with Psych; skipping this service'; return 1; }
            ruby -rpsych -e 'x=Psych.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: false); abort "Expected mapping" unless x.is_a?(Hash)' "$2"
            ;;
        *)
            mkdir -p "$TEMP/uci"
            cp "$2" "$TEMP/uci/$1" || return 1
            uci -c "$TEMP/uci" -t "$TEMP/uci-state" export "$1" > "$TEMP/uci-export" &&
            grep -q '^config ' "$TEMP/uci-export"
            ;;
    esac
}
restart() {
    /etc/init.d/"$1" restart || return 1
    # procd can restart successfully before the process has actually started.
    case "$1" in firewall) fw4 check ;; *)
        attempt=0
        while [ "$attempt" -lt 10 ]; do
            if ubus call service list "{\"name\":\"$1\"}" | jsonfilter -e '@.*.instances.*.running' | grep -qx true; then return 0; fi
            sleep 1
            attempt=$((attempt + 1))
        done
        return 1 ;;
    esac
}
failed=0
for service in smartdns AdGuardHome ddns-go vlmcsd firewall; do
    [ -x "/etc/init.d/$service" ] || { log "$service not installed; skipped"; continue; }
    case "$service" in
        AdGuardHome) entries='AdGuardHome.yaml|/etc/AdGuardHome.yaml' ;;
        ddns-go) entries='ddns-go|/etc/config/ddns-go
ddns-go.yaml|/etc/ddns-go/config.yaml' ;;
        *) entries="$service|/etc/config/$service" ;;
    esac
    stage="$TEMP/$service"
    mkdir -p "$stage" || exit 1
    printf '%s\n' "$entries" > "$stage/entries"
    valid=1
    while IFS='|' read -r name dest; do
        if ! curl -fL --proto '=https' --proto-redir '=https' --retry 2 --connect-timeout 10 --max-time 60 "$BASE_URL/$name" -o "$stage/$name" ||
           [ ! -s "$stage/$name" ] || ! validate "$name" "$stage/$name"; then
            log "$service: download/validation failed ($name); leaving configuration unchanged"
            valid=0
            break
        fi
    done < "$stage/entries"
    [ "$valid" = 1 ] || { failed=$((failed + 1)); continue; }
    # Back up every file before replacing any file for this service.
    while IFS='|' read -r name dest; do
        if [ -L "$dest" ]; then valid=0; break; fi
        if [ -e "$dest" ]; then
            cp -p "$dest" "$stage/$name.old" || { valid=0; break; }
        fi
        mkdir -p "$(dirname "$dest")" || { valid=0; break; }
    done < "$stage/entries"
    [ "$valid" = 1 ] || { log "$service: backup failed; unchanged"; failed=$((failed + 1)); continue; }
    : > "$stage/changed"
    while IFS='|' read -r name dest; do
        # Same-directory staging makes rename atomic and preserves existing permissions.
        pending=$(mktemp "${dest}.update.XXXXXX") || { valid=0; break; }
        if [ -e "$dest" ]; then cp -p "$dest" "$pending" || valid=0; fi
        if [ "$valid" != 1 ] || ! cat "$stage/$name" > "$pending" || ! mv "$pending" "$dest"; then
            rm -f "$pending"; valid=0; break
        fi
        printf '%s|%s\n' "$name" "$dest" >> "$stage/changed"
    done < "$stage/entries"
    if [ "$valid" = 1 ] && restart "$service"; then
        log "$service: updated and running"
    else
        failed=$((failed + 1))
        log "$service: failed; restoring configuration"
        restored=1
        while IFS='|' read -r name dest; do
            if [ -e "$stage/$name.old" ]; then
                cp -p "$stage/$name.old" "$dest" || restored=0
            else
                rm -f "$dest" || restored=0
            fi
        done < "$stage/changed"
        if [ "$restored" != 1 ]; then
            # Preserve backups when recovery fails; do not delete the only recovery copy.
            recovery=$(mktemp -d /tmp/update-config-recovery.XXXXXX) || {
                trap - EXIT
                log "Could not create recovery directory; backups retained at $TEMP"
                rmdir "$LOCK"
                exit 1
            }
            if ! mv "$stage" "$recovery/service"; then
                trap - EXIT
                log "Could not move recovery files; all backups retained at $TEMP"
                rmdir "$LOCK"
                exit 1
            fi
            log "Recovery incomplete; backups retained at $recovery"
        elif ! restart "$service"; then
            log "$service: old configuration restored, but service recovery failed"
        fi
    fi
done
log "Completed; failed services: $failed"
[ "$failed" = 0 ]
