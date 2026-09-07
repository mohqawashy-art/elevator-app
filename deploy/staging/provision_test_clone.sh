#!/usr/bin/env bash
# إنشاء/تحديث مجلد test المنفصل على السيرفر — مثل jama-elevator-app لكن لفرع التجربة.
#   bash deploy/staging/provision_test_clone.sh
#   bash deploy/staging/provision_test_clone.sh /custom/path

set -euo pipefail

TEST_DIR="${1:-$HOME/liftcore/test-elevator-app}"
BRANCH="staging/department-hubs"
REPO_URL="${REPO_URL:-https://github.com/mohqawashy-art/elevator-app.git}"

echo "==> LiftCore test clone"
echo "    Dir:    $TEST_DIR"
echo "    Branch: $BRANCH"
echo "    URL:    $REPO_URL"
echo ""

mkdir -p "$(dirname "$TEST_DIR")"

if [ -d "$TEST_DIR/.git" ]; then
  echo "==> تحديث clone موجود"
  cd "$TEST_DIR"
  git fetch origin "$BRANCH" -q
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
  git pull --ff-only "origin/$BRANCH"
else
  echo "==> استنساخ جديد"
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$TEST_DIR"
  cd "$TEST_DIR"
fi

REV="$(git rev-parse --short HEAD)"
echo ""
echo "==> test-elevator-app جاهز @ $REV"
echo "    لا تستخدم gcp_update هنا — للنشر:"
echo "    sudo bash $TEST_DIR/deploy/staging/deploy_staging.sh"
