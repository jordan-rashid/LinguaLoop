@echo off
setlocal EnableExtensions
title LinguaLoop
set "HERE=%~dp0"
cd /d "%HERE%"

rem ======================================================================
rem  LinguaLoop launcher for Windows. Double-click to run.
rem
rem    start_lingualoop.bat             normal start
rem    start_lingualoop.bat demo        reset the database + sample history first
rem    start_lingualoop.bat live        use the live translation service
rem    start_lingualoop.bat demo live   both
rem    start_lingualoop.bat nobrowser   do not open the browser automatically
rem
rem  First run: finds Python 3.12 (or 3.11), builds a private environment in
rem  the .venv folder, installs the packages and the French language model
rem  (a few minutes, needs internet). Later runs start in seconds.
rem ======================================================================

set "DEMO="
set "LIVE="
set "NOBROWSER="
:parse
if "%~1"=="" goto parsed
if /i "%~1"=="demo" set "DEMO=1"
if /i "%~1"=="live" set "LIVE=1"
if /i "%~1"=="nobrowser" set "NOBROWSER=1"
shift
goto parse
:parsed

rem (HERE was saved above because SHIFT also shifts %0)
set "VENV_PY=%HERE%.venv\Scripts\python.exe"

rem ---- 1. Does a usable environment already exist? ----------------------
if not exist "%VENV_PY%" goto make_venv
"%VENV_PY%" -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" >nul 2>&1
if not errorlevel 1 goto check_ready
echo.
echo The existing .venv folder uses an unsupported Python version.
echo Rebuilding it with Python 3.12 ...
rmdir /s /q ".venv"

rem ---- 2. Create the environment ----------------------------------------
:make_venv
set "PYCMD="
py -3.12 --version >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3.12"
if defined PYCMD goto have_python
py -3.11 --version >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3.11"
if defined PYCMD goto have_python
goto no_python

:have_python
echo.
echo Creating the LinguaLoop environment using %PYCMD% ...
%PYCMD% -m venv .venv
if errorlevel 1 goto fail_venv

rem ---- 3. Install packages if anything is missing -----------------------
:check_ready
"%VENV_PY%" -c "import flask, flask_sqlalchemy, requests, spacy; spacy.load('fr_core_news_md')" >nul 2>&1
if not errorlevel 1 goto start_app

echo.
echo First-time setup: installing packages and the French language model.
echo This takes a few minutes and needs an internet connection. Please wait ...
echo.
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail_install
"%VENV_PY%" -m spacy download fr_core_news_md
if errorlevel 1 goto fail_install

rem ---- 4. Start the app -------------------------------------------------
:start_app
if not defined DEMO goto skip_demo
echo.
echo Resetting the demo database (with 3 days of sample review history) ...
"%VENV_PY%" demo\reset_demo.py --seed-history
if errorlevel 1 goto fail_run
:skip_demo

netstat -ano | findstr /R /C:":5000 .*LISTENING" >nul
if not errorlevel 1 goto port_busy

set "LINGUALOOP_DEBUG=0"
if defined LIVE set "LINGUALOOP_TRANSLATION_PROVIDER=mymemory"

echo.
echo ==================================================================
echo  LinguaLoop is starting. Your browser will open in a few seconds.
if defined LIVE echo  Live translation is ON.
if defined DEMO echo  Demo mode: sample review history was loaded.
echo  Address: http://localhost:5000
echo  For the full demo setup (terminals, browser, code files), use start_demo.bat.
echo  Keep this window open while you use the app.
echo  To stop LinguaLoop, close this window or press Ctrl+C.
echo ==================================================================
echo.
if not defined NOBROWSER start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 6; Start-Process 'http://localhost:5000'"
"%VENV_PY%" run.py
echo.
echo LinguaLoop has stopped.
pause
exit /b 0

rem ---- Problems ---------------------------------------------------------
:no_python
echo.
echo Python 3.12 was not found on this computer.
echo.
where winget >nul 2>&1
if errorlevel 1 goto manual_python
echo I can install it for you now using the Windows installer (winget).
choice /c YN /n /m "Install Python 3.12 now? [Y/N] "
if errorlevel 2 goto manual_python
winget install -e --id Python.Python.3.12
echo.
echo When the install has finished, CLOSE this window and double-click
echo start_lingualoop.bat again.
pause
exit /b 0

:manual_python
echo Please install Python 3.12 from https://www.python.org/downloads/
echo During setup, tick the box that says Add python.exe to PATH.
echo Then double-click start_lingualoop.bat again.
pause
exit /b 1

:fail_venv
echo.
echo Could not create the environment. Make sure the folder is not inside a
echo zip file (unzip it first) and that you can write to it, then try again.
pause
exit /b 1

:fail_install
echo.
echo The install did not finish. The most common causes are:
echo   - no internet connection (the packages and language model download)
echo   - an unsupported Python version (a message mentioning Microsoft
echo     Visual C++ means this). Delete the .venv folder, install Python 3.12,
echo     and run this file again.
echo See the messages above for details.
pause
exit /b 1

:fail_run
echo.
echo Could not prepare the demo database. See the messages above.
pause
exit /b 1

:port_busy
echo.
echo Something is already using port 5000. If LinguaLoop is already running
echo in another window, opening http://localhost:5000 now.
echo Otherwise close the other program and run this file again.
start "" "http://localhost:5000"
pause
exit /b 1
