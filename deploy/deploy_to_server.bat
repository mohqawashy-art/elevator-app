@echo off
title LiftCore - رفع على السيرفر
set "SERVER=2.29.6.41"
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
echo اذا فشل SSH، اتصل بـ Hetzner Console ^> SSH
echo وشغّل: bash deploy/server_update_now.sh
echo.

ssh -o StrictHostKeyChecking=accept-new %USER%@%SERVER% "cd %APP% 2>/dev/null || cd /var/www/elevator-app; bash deploy/server_update_now.sh"

if errorlevel 1 (
  echo.
  echo فشل الاتصال. جرّب SSH يدوياً:
  echo   cd ~/liftcore/elevator-app ^&^& bash deploy/server_update_now.sh
  pause
  exit /b 1
)

echo.
echo تم الرفع. تحقق من:
echo   https://app.liftcoreapp.com/installation
echo   https://app.liftcoreapp.com/purchase-orders
pause
