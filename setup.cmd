@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

title LiftCore - اعداد اختصار الشركة

:MENU
cls
echo.
echo   ========================================
echo      LiftCore - اعداد اختصار سطح المكتب
echo   ========================================
echo.
echo     1) JAMA
echo     2) LiftCore (الرئيسي)
echo     3) شركة جديدة (ادخال يدوي)
echo     0) خروج
echo.
set "CH="
set /p CH="   اختر رقم: "

if "%CH%"=="1" goto JAMA
if "%CH%"=="2" goto MAIN
if "%CH%"=="3" goto CUSTOM
if "%CH%"=="0" exit /b 0
goto MENU

:JAMA
cscript //nologo "%~dp0desktop\Create-Shortcut.vbs" "JAMA" "https://jama.liftcoreapp.com/login" "" 1
goto DONE

:MAIN
cscript //nologo "%~dp0desktop\Create-Shortcut.vbs" "LiftCore" "https://app.liftcoreapp.com/login" "" 1
goto DONE

:CUSTOM
echo.
set "CNAME="
set /p CNAME="   اسم الشركة (مثال: شركة النور): "
if "%CNAME%"=="" goto MENU
set "CURL="
set /p CURL="   رابط الموقع (مثال: demo.liftcoreapp.com): "
if "%CURL%"=="" goto MENU
cscript //nologo "%~dp0desktop\Create-Shortcut.vbs" "%CNAME%" "%CURL%" "" 1
goto DONE

:DONE
echo.
echo   ----------------------------------------
echo   تم انشاء الاختصار على سطح المكتب.
echo   للتثبيت على شريط المهام:
echo   كليك يمين على الاختصار - تثبيت على شريط المهام
echo   ----------------------------------------
echo.
pause
endlocal
