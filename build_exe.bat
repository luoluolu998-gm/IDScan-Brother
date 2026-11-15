@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "LOG=%ROOT%\build_log.txt"
set "DIST=%ROOT%\dist"
set "WORK=%ROOT%\build"
set "EXE=%DIST%\IDScan_Brother_3.0.exe"

echo =====================================================
echo IDScan Brother 3.0 - BUILD
echo =====================================================
echo.
>"%LOG%" echo IDScan Brother 3.0 build log
>>"%LOG%" echo Date: %date% %time%
>>"%LOG%" echo Working directory: %CD%

if not exist "%ROOT%\main.py" goto SOURCE_MISSING
if not exist "%ROOT%\requirements.txt" goto REQUIREMENTS_MISSING
if not exist "%DIST%" mkdir "%DIST%"
if not exist "%WORK%" mkdir "%WORK%"

echo [1/4] Checking Python...
where python >>"%LOG%" 2>&1
if errorlevel 1 goto NO_PYTHON
python --version >>"%LOG%" 2>&1
if errorlevel 1 goto NO_PYTHON
python -m pip --version >>"%LOG%" 2>&1
if errorlevel 1 goto NO_PIP

echo [2/4] Installing requirements...
python -m pip install -r "%ROOT%\requirements.txt" >>"%LOG%" 2>&1
if errorlevel 1 goto BUILD_FAILED

echo [3/4] Running PyInstaller. Please wait...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "IDScan_Brother_3.0" --distpath "%DIST%" --workpath "%WORK%" --specpath "%WORK%" --collect-all customtkinter --collect-all cv2 --collect-all PIL --collect-all reportlab "%ROOT%\main.py" >>"%LOG%" 2>&1
if errorlevel 1 goto BUILD_FAILED
if not exist "%EXE%" goto EXE_MISSING

echo [4/4] BUILD SUCCEEDED.
echo Output: "%EXE%"
echo Log: "%LOG%"
echo.
echo Copy the EXE beside naps2.exe. Keep NAPS2 app and data folders unchanged.
pause
exit /b 0

:SOURCE_MISSING
echo ERROR: main.py was not found in this folder.
>>"%LOG%" echo ERROR: main.py missing.
goto FAILED
:REQUIREMENTS_MISSING
echo ERROR: requirements.txt was not found in this folder.
>>"%LOG%" echo ERROR: requirements.txt missing.
goto FAILED
:NO_PYTHON
echo ERROR: Python command was not found. See build_log.txt.
goto FAILED
:NO_PIP
echo ERROR: pip is unavailable. See build_log.txt.
goto FAILED
:EXE_MISSING
echo ERROR: PyInstaller finished but EXE was not found. See build_log.txt.
goto FAILED
:BUILD_FAILED
echo BUILD FAILED. See build_log.txt for the full error.
goto FAILED
:FAILED
echo.
echo Log file: "%LOG%"
echo The window will stay open. Copy build_log.txt and send it for diagnosis.
pause
exit /b 1
