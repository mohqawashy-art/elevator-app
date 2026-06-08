@echo off
title LiftCore - رفع على السيرفر
set "SERVER=34.18.56.21"
set "USER=info"
set "APP=~/liftcore/elevator-app"

echo.
echo ================================================
echo   رفع LiftCore على السيرفر
echo   https://app.liftcoreapp.com
echo ================================================
echo.
echo السيرفر: %USER%@%SERVER%
echo.
echo اذا فشل SSH، استخدم Google Cloud Console ^> SSH
echo وشغّل: bash deploy/gcp_update.sh
echo.

ssh -o StrictHostKeyChecking=accept-new %USER%@%SERVER% "cd %APP% 2>/dev/null || cd /var/www/elevator-app; bash deploy/gcp_update.sh"

if errorlevel 1 (
  echo.
  echo فشل الاتصال. جرّب من GCP Console:
  echo   cd ~/liftcore/elevator-app ^&^& bash deploy/gcp_update.sh
  pause
  exit /b 1
)

echo.
echo تم الرفع. افتح https://app.liftcoreapp.com/purchase-orders
pause
