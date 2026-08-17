@echo off
title EXL Banking AI — Rate Change Intelligence
color 0A

:: ── Always run from the folder containing this bat file ──────
cd /d "%~dp0"

echo.
echo ============================================================
echo   EXL Agentic Rate Change Intelligence System v3.0
echo   EXL Hackathon 2026
echo ============================================================
echo.
echo [INFO] Working directory: %CD%
echo.

:: ── Find Python ──────────────────────────────────────────────
set PYTHON=
if exist "C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe" (
    set PYTHON=C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe
) else if exist "C:\Users\vmuser\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON=C:\Users\vmuser\AppData\Local\Programs\Python\Python313\python.exe
) else if exist "C:\Users\vmuser\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON=C:\Users\vmuser\AppData\Local\Programs\Python\Python312\python.exe
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo.
        echo [ERROR] Python not found. Please install Python 3.11 or newer.
        echo         Check: C:\Users\vmuser\AppData\Local\Programs\Python\
        echo.
        goto :end
    )
)
echo [OK] Python: %PYTHON%
echo.

:: ── Check GROQ_API_KEY ────────────────────────────────────────
if "%GROQ_API_KEY%"=="" (
    echo [SETUP] GROQ_API_KEY is not set.
    set /p GROQ_API_KEY="       Paste your Groq API key (starts with gsk_): "
    echo.
)
if "%GROQ_API_KEY%"=="" (
    echo.
    echo [WARNING] No API key entered.
    echo           Get a free key at: https://console.groq.com
    echo           The app will start but LLM features will not work.
    echo.
)

:: ── Clean stale bytecode cache ────────────────────────────────
echo [CLEANUP] Clearing Python bytecode cache...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
echo [OK] Cache cleared.

:: ── Clean old incompatible index files ───────────────────────
echo [CLEANUP] Removing old index files (will rebuild fresh)...
if exist "data\sop.faiss"         del /f /q "data\sop.faiss"         2>nul
if exist "data\sop_vectors.npy"   del /f /q "data\sop_vectors.npy"   2>nul
if exist "data\sop_vectorizer.pkl" del /f /q "data\sop_vectorizer.pkl" 2>nul
if exist "data\sop_bm25.pkl"      del /f /q "data\sop_bm25.pkl"      2>nul
echo [OK] Old indexes removed.
echo.

:: ── Dependency checks ─────────────────────────────────────────
echo Checking dependencies...
echo.
set INSTALL_ERRORS=0

echo [1/6] scikit-learn...
%PYTHON% -c "import sklearn" >nul 2>&1
if %errorlevel% neq 0 (
    echo       Not found. Installing...
    %PYTHON% -m pip install scikit-learn --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] scikit-learn install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] scikit-learn installed.
    )
) else (
    echo       [OK] Already installed.
)

echo [2/6] groq...
%PYTHON% -c "import groq" >nul 2>&1
if %errorlevel% neq 0 (
    echo       Not found. Installing...
    %PYTHON% -m pip install groq --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] groq install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] groq installed.
    )
) else (
    echo       [OK] Already installed.
)

echo [3/6] streamlit...
%PYTHON% -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo       Not found. Installing...
    %PYTHON% -m pip install streamlit --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] streamlit install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] streamlit installed.
    )
) else (
    echo       [OK] Already installed.
)

echo [4/6] pandas...
%PYTHON% -c "import pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo       Not found. Installing...
    %PYTHON% -m pip install pandas --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] pandas install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] pandas installed.
    )
) else (
    echo       [OK] Already installed.
)

echo [5/6] rank-bm25 and pdfplumber...
%PYTHON% -c "import rank_bm25" >nul 2>&1
if %errorlevel% neq 0 (
    echo       rank-bm25 not found. Installing...
    %PYTHON% -m pip install rank-bm25 --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] rank-bm25 install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] rank-bm25 installed.
    )
) else (
    echo       [OK] rank-bm25 already installed.
)
%PYTHON% -c "import pdfplumber" >nul 2>&1
if %errorlevel% neq 0 (
    echo       pdfplumber not found. Installing...
    %PYTHON% -m pip install pdfplumber --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] pdfplumber install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] pdfplumber installed.
    )
) else (
    echo       [OK] pdfplumber already installed.
)

echo [6/6] python-docx...
%PYTHON% -c "import docx" >nul 2>&1
if %errorlevel% neq 0 (
    echo       Not found. Installing...
    %PYTHON% -m pip install python-docx --break-system-packages
    if %errorlevel% neq 0 (
        echo       [ERROR] python-docx install FAILED. See error above.
        set INSTALL_ERRORS=1
    ) else (
        echo       [OK] python-docx installed.
    )
) else (
    echo       [OK] Already installed.
)

echo.
if "%INSTALL_ERRORS%"=="1" (
    echo ============================================================
    echo   [WARNING] Some packages failed to install.
    echo   The app will try to start anyway.
    echo   If it crashes, check the errors above and install manually.
    echo ============================================================
    echo.
) else (
    echo [OK] All dependencies ready.
    echo.
)

:: ── Generate data (always run to ensure files exist) ─────────
echo [SETUP] Creating data folder...
if not exist "data" mkdir data

echo [SETUP] Generating portfolio CSV and competitor rates...
%PYTHON% scripts\generate_portfolio.py
if %errorlevel% neq 0 (
    echo [ERROR] generate_portfolio.py FAILED. See error above.
) else (
    echo [OK] Portfolio data ready.
)
echo.

echo [SETUP] Generating SOP Word documents...
%PYTHON% scripts\create_sops.py
if %errorlevel% neq 0 (
    echo [ERROR] create_sops.py FAILED. See error above.
) else (
    echo [OK] SOP documents ready.
)
echo.

echo [INFO] Files in data\ folder:
dir /b data\ 2>nul || echo       (data folder is empty or missing)
echo.

:: ── Launch app ────────────────────────────────────────────────
echo ============================================================
echo   Starting app at http://localhost:8501
echo   First run builds the search index (~15 sec). Normal!
echo   If the app crashes, the error will show below.
echo   Press Ctrl+C in this window to stop.
echo ============================================================
echo.

%PYTHON% -m streamlit run chatbot/app.py --server.headless false
set APP_EXIT=%errorlevel%

echo.
if %APP_EXIT% neq 0 (
    echo ============================================================
    echo   [ERROR] App stopped with error code: %APP_EXIT%
    echo   Scroll up to see the full error message.
    echo ============================================================
) else (
    echo [OK] App closed cleanly.
)

:end
echo.
echo Press any key to close this window...
pause >nul
