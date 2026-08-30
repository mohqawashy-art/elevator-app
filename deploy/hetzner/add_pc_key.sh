#!/bin/bash
# One-shot: allow this PC's SSH key for root on liftcore-prod.
set -euo pipefail
mkdir -p /root/.ssh
chmod 700 /root/.ssh
KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEtT1cPUhUStrHpRYY5lnSoHmKfYBe4eZdFwaFzan1/f liftcore-home-pc'
touch /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
grep -qxF "$KEY" /root/.ssh/authorized_keys || echo "$KEY" >> /root/.ssh/authorized_keys
# allow root key login
if [ -f /etc/ssh/sshd_config ]; then
  sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config || true
  sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config || true
  systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
fi
echo OK
cat /root/.ssh/authorized_keys
