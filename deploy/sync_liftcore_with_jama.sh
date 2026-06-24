#!/usr/bin/env bash
# مزامنة LiftCore مع نفس كود جما (نفس المستودع — بدون لمس قاعدة البيانات)
# على السيرفر:
#   bash deploy/sync_liftcore_with_jama.sh
#   bash deploy/sync_liftcore_with_jama.sh ~/liftcore/elevator-app ~/liftcore/jama-elevator-app

set -euo pipefail

LIFT_DIR="${1:-$HOME/liftcore/elevator-app}"
JAMA_DIR="${2:-$HOME/liftcore/jama-elevator-app}"

if [ ! -d "$JAMA_DIR/.git" ]; then
  echo "ERROR: لا يوجد مستودع git في $JAMA_DIR"
  exit 1
fi
if [ ! -d "$LIFT_DIR/.git" ]; then
  echo "ERROR: لا يوجد مستودع git في $LIFT_DIR"
  exit 1
fi

echo "==> مزامنة LiftCore مع جما"
echo "    جما:     $JAMA_DIR"
echo "    LiftCore: $LIFT_DIR"

cd "$JAMA_DIR"
echo "==> تحديث جما من GitHub"
git fetch origin main -q
git pull --ff-only origin main
JAMA_REV="$(git rev-parse HEAD)"
echo "    جما @ ${JAMA_REV:0:7}"

cd "$LIFT_DIR"
echo "==> تحديث LiftCore إلى نفس الـ commit"
git fetch origin main -q
if git merge-base --is-ancestor HEAD "$JAMA_REV" 2>/dev/null; then
  git merge --ff-only "$JAMA_REV"
elif [ "$(git rev-parse HEAD)" = "$JAMA_REV" ]; then
  echo "    LiftCore محدّث مسبقاً"
else
  git pull --ff-only origin main
  LIFT_REV="$(git rev-parse HEAD)"
  if [ "$LIFT_REV" != "$JAMA_REV" ]; then
    echo "WARN: LiftCore @ ${LIFT_REV:0:7} ≠ جما @ ${JAMA_REV:0:7} — جرّب: cd $LIFT_DIR && git pull --ff-only origin main"
  fi
fi

export SERVICE_NAME=liftcore
export APP_DIR="$LIFT_DIR"
echo "==> نشر LiftCore (gcp_update.sh)"
bash "$LIFT_DIR/deploy/gcp_update.sh"

echo ""
echo "==> تم. LiftCore @ $(git -C "$LIFT_DIR" rev-parse --short HEAD)"
echo "    جما      @ $(git -C "$JAMA_DIR" rev-parse --short HEAD)"
echo "    اختبر: https://app.liftcoreapp.com"
