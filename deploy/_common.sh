#!/usr/bin/env bash
# دوال مشتركة لسكربتات النشر على السيرفر
# shellcheck shell=bash

lc_resolve_venv() {
  local app_dir="$1"
  local service_name="${2:-liftcore}"

  if [ -n "${VENV:-}" ] && [ -x "${VENV}/bin/python" ]; then
    echo "$VENV"
    return 0
  fi

  local candidate
  for candidate in \
    "$app_dir/.venv" \
    "$HOME/liftcore/venv" \
    "/home/info/liftcore/venv"; do
    if [ -x "$candidate/bin/python" ]; then
      echo "$candidate"
      return 0
    fi
  done

  if command -v systemctl >/dev/null 2>&1; then
    local exec_line gunicorn_bin venv_root
    exec_line="$(systemctl show "$service_name" -p ExecStart --value 2>/dev/null || true)"
    gunicorn_bin="$(printf '%s\n' "$exec_line" | grep -oE '[^ ]+/gunicorn' | head -1 || true)"
    if [ -n "$gunicorn_bin" ] && [ -x "$gunicorn_bin" ]; then
      venv_root="$(dirname "$(dirname "$gunicorn_bin")")"
      if [ -x "$venv_root/bin/python" ]; then
        echo "$venv_root"
        return 0
      fi
    fi
  fi

  echo "$app_dir/.venv"
}

lc_fix_platform_env_perms() {
  local platform_env="${1:-/etc/liftcore/platform.env}"
  local run_user="${SUDO_USER:-$USER}"

  if [ ! -f "$platform_env" ]; then
    return 0
  fi

  if getent group "$run_user" >/dev/null 2>&1; then
    sudo chown "root:${run_user}" "$platform_env" 2>/dev/null || sudo chown "${run_user}:${run_user}" "$platform_env"
  else
    sudo chown "${run_user}:${run_user}" "$platform_env" 2>/dev/null || true
  fi
  sudo chmod 640 "$platform_env" 2>/dev/null || chmod 640 "$platform_env" 2>/dev/null || true
}

lc_pip_install_requirements() {
  local venv="$1"
  local app_dir="$2"

  if [ ! -x "$venv/bin/pip" ]; then
    echo "ERROR: pip غير موجود في $venv"
    return 1
  fi

  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  pip install -q --upgrade pip
  if [ -f "$app_dir/requirements.txt" ]; then
    pip install -q -r "$app_dir/requirements.txt"
  else
    pip install -q flask flask-sqlalchemy flask-migrate gunicorn werkzeug cryptography sentry-sdk
  fi
  python -c "import flask_migrate; import sentry_sdk; print('  deps OK: flask_migrate, sentry_sdk')"
}
