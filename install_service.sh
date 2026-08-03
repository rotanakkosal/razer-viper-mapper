#!/bin/bash
#
# Install / uninstall the Viper Mapper background service (LaunchAgent).
#
#   ./install_service.sh            install and start at login
#   ./install_service.sh uninstall  stop and remove
#   ./install_service.sh status     show whether it's running
#   ./install_service.sh restart    reload after code changes
#   ./install_service.sh logs       tail the service log
#
set -euo pipefail

LABEL="com.vipermapper.agent"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_FILE="$HOME/Library/Logs/viper-mapper.log"
PYTHON="$REPO_DIR/.venv/bin/python"

# launchd needs the interpreter's real path, not the venv symlink: TCC
# (Accessibility / Input Monitoring) is granted against the actual binary.
resolve_python() {
    if [ ! -x "$PYTHON" ]; then
        echo "ERROR: no venv Python at $PYTHON" >&2
        echo "Create it first:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
        exit 1
    fi
    REAL_PYTHON="$("$PYTHON" -c 'import os,sys; print(os.path.realpath(sys.base_prefix + "/bin/python3"))')"
}

port_from_settings() {
    "$PYTHON" - <<'PY' 2>/dev/null || echo 8080
import json, os
try:
    with open(os.path.join(os.getcwd(), "settings.json")) as f:
        print(int(json.load(f).get("server", {}).get("port", 8080)))
except Exception:
    print(8080)
PY
}

# A hand-started `python app.py` holding the port would make the agent
# crash-loop forever, so clear it out first.
free_the_port() {
    local port pids
    port="$(cd "$REPO_DIR" && port_from_settings)"
    pids="$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null || true)"
    [ -z "$pids" ] && return 0

    echo "Port $port is in use by PID(s): $pids"
    echo "That is almost certainly an app.py you started by hand."
    read -r -p "Stop it so the service can take over? [y/N] " reply
    case "$reply" in
        [yY]*)
            # shellcheck disable=SC2086
            kill $pids 2>/dev/null || true
            sleep 1
            echo "Stopped."
            ;;
        *)
            echo "Aborted — free port $port yourself, then re-run." >&2
            exit 1
            ;;
    esac
}

generate_plist() {
    cat <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$REPO_DIR/app.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <!-- Don't hot-loop if it crashes (e.g. permissions not yet granted). -->
    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>

    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
PLIST_EOF
}

cmd_install() {
    resolve_python
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

    # Tear down a previous agent before replacing its plist.
    if [ -f "$PLIST" ]; then
        launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
    fi
    free_the_port

    generate_plist > "$PLIST"
    plutil -lint "$PLIST" >/dev/null || { echo "Generated plist is invalid" >&2; exit 1; }

    launchctl bootstrap "gui/$UID" "$PLIST"
    echo "Installed and started: $LABEL"
    echo
    echo "──────────────────────────────────────────────────────────────"
    echo "REQUIRED — grant permissions to the Python binary"
    echo "──────────────────────────────────────────────────────────────"
    echo "launchd is now the launcher, so your Terminal's Accessibility"
    echo "grant no longer applies. Add this binary to BOTH lists in"
    echo "System Settings > Privacy & Security:"
    echo
    echo "    Accessibility        (+ button)"
    echo "    Input Monitoring     (+ button)"
    echo
    echo "In the file picker press Cmd+Shift+G and paste:"
    echo
    echo "    $REAL_PYTHON"
    echo
    echo "Then run:  ./install_service.sh restart"
    echo "──────────────────────────────────────────────────────────────"
    echo
    echo "UI:   http://localhost:8080"
    echo "Logs: $LOG_FILE"
    echo
    echo "Turn on 'Start Automatically' in the UI so detection resumes"
    echo "at login without opening the browser."
}

cmd_uninstall() {
    launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Uninstalled: $LABEL (settings and profiles kept)"
}

cmd_restart() {
    launchctl kickstart -k "gui/$UID/$LABEL"
    echo "Restarted: $LABEL"
}

cmd_status() {
    if launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1; then
        launchctl print "gui/$UID/$LABEL" | grep -E "^\s+(state|pid|last exit code) " || true
    else
        echo "Not installed. Run: ./install_service.sh"
    fi
}

case "${1:-install}" in
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    restart)   cmd_restart ;;
    status)    cmd_status ;;
    logs)      tail -f "$LOG_FILE" ;;
    plist)     resolve_python; generate_plist ;;
    *)
        echo "Usage: $0 [install|uninstall|restart|status|logs|plist]" >&2
        exit 1
        ;;
esac
