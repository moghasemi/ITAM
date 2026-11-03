@echo off
REM ==========================================================================
REM  اجرای سامانه مدیریت دارایی و نگهداری فناوری اطلاعات (ITAM)
REM  این فایل سامانه را روی همه کارت‌های شبکه سرور (0.0.0.0) در پورت 8000 اجرا می‌کند.
REM ==========================================================================
setlocal
cd /d "%~dp0.."

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if "%ITAM_DEBUG%"=="" set ITAM_DEBUG=0
if "%ITAM_ALLOWED_HOSTS%"=="" set ITAM_ALLOWED_HOSTS=*
if "%ITAM_PORT%"=="" set ITAM_PORT=8000

set PYTHON=python
if exist ".venv\Scripts\python.exe" set PYTHON=.venv\Scripts\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe

echo [ITAM] بررسی پایگاه داده و اعمال مهاجرت‌ها...
%PYTHON% manage.py migrate --noinput
if errorlevel 1 (
  echo [ITAM] خطا در مهاجرت پایگاه داده. اجرا متوقف شد.
  exit /b 1
)

echo [ITAM] جمع‌آوری فایل‌های ایستا...
%PYTHON% manage.py collectstatic --noinput >nul 2>&1

echo [ITAM] راه‌اندازی سرور روی پورت %ITAM_PORT% ...
%PYTHON% -c "import waitress" >nul 2>&1
if errorlevel 1 goto devserver

%PYTHON% -m waitress --host=0.0.0.0 --port=%ITAM_PORT% --threads=8 --channel-timeout=120 config.wsgi:application
goto end

:devserver
echo [ITAM] هشدار: بسته waitress نصب نیست؛ سرور توسعه جنگو اجرا می‌شود.
echo [ITAM] برای محیط عملیاتی دستور زیر را اجرا کنید:  pip install waitress
%PYTHON% manage.py runserver 0.0.0.0:%ITAM_PORT% --noreload

:end
endlocal
