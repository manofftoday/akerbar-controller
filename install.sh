#!/usr/bin/bash
set -euo pipefail

INSTALL_ROOT="/opt/akerbar-controller"
SHARE_DIR="/usr/share/akerbar-controller"
SERVICE_DIR="/etc/systemd/system"
LOCAL_SBIN="/usr/local/sbin"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-$(id -un)}"
TARGET_HOME=""

function resolve_target_home() {
  if command -v getent >/dev/null 2>&1; then
    TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
  else
    TARGET_HOME="$(eval echo "~$TARGET_USER")"
  fi

  if [ -z "$TARGET_HOME" ] || [ ! -d "$TARGET_HOME" ]; then
    error "Unable to resolve home directory for user '$TARGET_USER'."
  fi
}

function error() {
  echo "ERROR: $*" >&2
  exit 1
}

function ensure_root() {
  if [ "$(id -u)" -ne 0 ]; then
    error "This installer must be run as root. Use sudo ./install.sh"
  fi
}

function install_prerequisites() {
  echo "[*] Installing prerequisites..."

  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y python3 python3-pip python3-requests python3-serial uhubctl || true
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-pip python3-requests python3-serial uhubctl || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip python3-requests python3-serial uhubctl || true
  else
    echo "[!] No supported package manager found. You must install these packages manually:"
    echo "    python3, pip, requests, pyserial, uhubctl"
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    error "python3 is not installed. Install Python 3 before running this script."
  fi

  if ! python3 -c 'import requests, serial' >/dev/null 2>&1; then
    echo "[!] Installing Python dependencies with pip..."
    python3 -m pip install --upgrade pip
    python3 -m pip install requests pyserial
  fi

  if ! command -v uhubctl >/dev/null 2>&1; then
    echo "[!] uhubctl was not found. Please install uhubctl on your system for USB hub power control."
  fi
}

function deploy_files() {
  echo "[*] Deploying application files..."
  mkdir -p "$INSTALL_ROOT" "$SHARE_DIR" "$LOCAL_SBIN"

  cp -r "$SRC_DIR/opt/." "$INSTALL_ROOT/"
  chmod 755 "$INSTALL_ROOT"/*.py

  cp "$SRC_DIR/opt/akerbar-control.py" "$LOCAL_SBIN/akerbar-control"
  chmod 755 "$LOCAL_SBIN/akerbar-control"

  cp "$SRC_DIR/systemd/akerbar-controller.service" "$SERVICE_DIR/"
  cp "$SRC_DIR/systemd/akerbar-telegram.service" "$SERVICE_DIR/"
  chmod 644 "$SERVICE_DIR"/akerbar-*.service
}

function install_bash_profile() {
  echo "[*] Installing bash profile for $TARGET_USER..."

  if [ -f "$TARGET_HOME/.bash_profile" ]; then
    cp "$TARGET_HOME/.bash_profile" "$TARGET_HOME/.bash_profile.bak.$(date +%Y%m%d%H%M%S)"
  fi

  cat > "$TARGET_HOME/.bash_profile" <<EOF
if [ "\$(tty)" = "/dev/tty1" ]; then
    clear
    sleep 3

    # wait until VT is active
    while ! fgconsole 1>/dev/null 2>&1; do
        sleep 1
    done

    python3 "$INSTALL_ROOT/akerbar-display.py"
fi
EOF

  chown "$TARGET_USER":"$TARGET_USER" "$TARGET_HOME/.bash_profile"
  chmod 644 "$TARGET_HOME/.bash_profile"
}

function configure_systemd() {
  if command -v systemctl >/dev/null 2>&1; then
    echo "[*] Reloading systemd daemon and enabling services..."
    systemctl daemon-reload
    systemctl enable akerbar-controller.service
    systemctl enable akerbar-telegram.service
    echo "[*] Starting services..."
    systemctl restart akerbar-controller.service || true
    systemctl restart akerbar-telegram.service || true
  else
    echo "[!] systemctl not available. Services were copied, but you must enable/start them manually."
  fi
}

function show_summary() {
  echo ""
  echo "Installation complete."
  echo "  REBOOT your system to apply changes."
  echo ""
  echo "  Installed files to: $INSTALL_ROOT"
  echo "  Shared state directory: $SHARE_DIR"
  echo "  Installed bash profile: $TARGET_HOME/.bash_profile"
  echo "  Systemd units: $SERVICE_DIR/akerbar-controller.service, $SERVICE_DIR/akerbar-telegram.service"
  echo ""
  echo "If systemd is available, services were enabled and restarted."
  echo "If needed, you can manage them with:"
  echo "  systemctl status akerbar-controller.service"
  echo "  systemctl status akerbar-telegram.service"
}

ensure_root
resolve_target_home
install_prerequisites
deploy_files
install_bash_profile
configure_systemd
show_summary
