@echo off
setlocal EnableExtensions
title LinguaLoop demo
set "HERE=%~dp0"
cd /d "%HERE%"

rem ======================================================================
rem  LinguaLoop demo setup for Windows. Double-click to run.
rem
rem    start_demo.bat         built-in dictionaries (works offline)
rem    start_demo.bat live    live translation service
rem
rem  Opens everything for a demo, in this order:
rem    1. Terminal 1  - the app server (start_lingualoop.bat does any setup)
rem    2. Terminal 2  - environment active, demo database reset with sample
rem                     review history; stays open for running the tests
rem                     (Terminals 1 and 2 open as two tabs of one Windows
rem                     Terminal window; without Windows Terminal, as two
rem                     separate windows)
rem    3. Browser     - http://localhost:5000
rem    4. Editor      - the main code files as tabs, then the sample passage
rem                     (Visual Studio Code if installed, otherwise Notepad)
rem
rem  This window only coordinates. You can close it once everything is open;
rem  the other windows keep running.
rem ======================================================================

set "MODE_ARG="
set "MODE_NAME=built-in dictionaries"
if /i "%~1"=="live" set "MODE_ARG=live"
if /i "%~1"=="live" set "MODE_NAME=live translation"

echo.
echo LinguaLoop demo setup  (%MODE_NAME%)
echo.

rem Windows Terminal (wt) lets both terminals share one window as tabs. It is
rem built into Windows 11; on Windows 10 it is a free Microsoft Store app.
rem A unique window name keeps these tabs out of any older Terminal window.
set "WTWIN=LinguaLoop-%RANDOM%"
set "USE_WT="
where wt >nul 2>&1
if not errorlevel 1 set "USE_WT=1"
set "TERM_NOTE=two separate windows (install Windows Terminal for tabs)"
if defined USE_WT set "TERM_NOTE=two tabs in one Windows Terminal window"

rem ---- 1. Terminal 1: the server ----------------------------------------
echo [1/4] Opening Terminal 1 (the app server) ...
if defined USE_WT goto t1_tab
start "LinguaLoop - Terminal 1 (server)" cmd /c start_lingualoop.bat nobrowser %MODE_ARG%
goto t1_done
:t1_tab
wt -w %WTWIN% new-tab --title "Terminal 1 (server)" -d . cmd /c start_lingualoop.bat nobrowser %MODE_ARG%
:t1_done

echo       Waiting for the server to come up. The first time on this computer
echo       this includes installing everything, which can take a few minutes.
set /a WAITED=0
:wait_server
netstat -ano | findstr /R /C:":5000 .*LISTENING" >nul
if not errorlevel 1 goto server_up
if %WAITED% GEQ 900 goto wait_timeout
<nul set /p "=."
ping -n 4 127.0.0.1 >nul
set /a WAITED+=3
goto wait_server

:server_up
echo.
echo       Server is running.

rem ---- 2. Terminal 2: environment active + reset ------------------------
echo [2/4] Opening Terminal 2 (environment active, demo data reset) ...
if defined USE_WT goto t2_tab
start "LinguaLoop - Terminal 2 (commands)" cmd /k "call .venv\Scripts\activate.bat && python demo\reset_demo.py --seed-history"
goto t2_done
:t2_tab
wt -w %WTWIN% new-tab --title "Terminal 2 (commands)" -d . cmd /k "title Terminal 2 (commands) && call .venv\Scripts\activate.bat && python demo\reset_demo.py --seed-history"
:t2_done
ping -n 6 127.0.0.1 >nul

rem ---- 3. Browser --------------------------------------------------------
echo [3/4] Opening the browser at http://localhost:5000 ...
start "" "http://localhost:5000"
ping -n 3 127.0.0.1 >nul

rem ---- 4. Editor: code files in order, then the sample passage ----------
echo [4/4] Opening the code files ...
set "CODEEXE="
set "EDITOR_NOTE="

rem Look for VS Code itself in the usual install folders first (this does
rem not depend on the PATH setting, which a double-click can miss).
if exist "%LocalAppData%\Programs\Microsoft VS Code\Code.exe" set "CODEEXE=%LocalAppData%\Programs\Microsoft VS Code\Code.exe"
if not defined CODEEXE if exist "%ProgramFiles%\Microsoft VS Code\Code.exe" set "CODEEXE=%ProgramFiles%\Microsoft VS Code\Code.exe"
if not defined CODEEXE if exist "%ProgramFiles(x86)%\Microsoft VS Code\Code.exe" set "CODEEXE=%ProgramFiles(x86)%\Microsoft VS Code\Code.exe"
if defined CODEEXE goto open_vscode

where code >nul 2>&1
if not errorlevel 1 goto open_code_cmd
goto open_notepad

:open_vscode
echo       Found Visual Studio Code: %CODEEXE%
start "" "%CODEEXE%" "." "app\__init__.py" "app\models.py" "app\services\extraction.py" "app\services\scheduler.py" "app\services\translation.py" "app\routes.py" "demo\demo_passage.txt"
set "EDITOR_NOTE=Visual Studio Code: code files as tabs, sample passage last"
goto done

:open_code_cmd
echo       Found the "code" command on the PATH.
call code "." "app\__init__.py" "app\models.py" "app\services\extraction.py" "app\services\scheduler.py" "app\services\translation.py" "app\routes.py" "demo\demo_passage.txt"
if errorlevel 1 goto open_notepad
set "EDITOR_NOTE=Visual Studio Code: code files as tabs, sample passage last"
goto done

:open_notepad
echo       Visual Studio Code was not found on this computer.
echo       Opening each file in Notepad instead, in order.
start "" notepad "app\__init__.py"
ping -n 2 127.0.0.1 >nul
start "" notepad "app\models.py"
ping -n 2 127.0.0.1 >nul
start "" notepad "app\services\extraction.py"
ping -n 2 127.0.0.1 >nul
start "" notepad "app\services\scheduler.py"
ping -n 2 127.0.0.1 >nul
start "" notepad "app\services\translation.py"
ping -n 2 127.0.0.1 >nul
start "" notepad "app\routes.py"
ping -n 2 127.0.0.1 >nul
start "" notepad "demo\demo_passage.txt"
set "EDITOR_NOTE=Notepad: one window per file (install Visual Studio Code for tabs)"
goto done

:done
echo.
echo ==================================================================
echo  Everything is open:
echo    Terminals   %TERM_NOTE%
echo    Terminal 1  server (leave it running; close it to stop the app)
echo    Terminal 2  environment active, demo data reset
echo                (run the tests here:  python -m pytest tests -q)
echo    Browser     http://localhost:5000
echo    Editor      %EDITOR_NOTE%
echo  Tip: press Ctrl and + in the browser to zoom to about 125 percent.
echo ==================================================================
echo.
pause
exit /b 0

:wait_timeout
echo.
echo The server did not start within 15 minutes. Look at the Terminal 1
echo window for the reason (for example a failed install), fix it, and run
echo this file again.
pause
exit /b 1
