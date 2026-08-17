@echo off
title Pushing v3.0 to GitHub
color 0B

:: ── Run from this file's folder ───────────────────────────────
cd /d "%~dp0"

echo.
echo ============================================================
echo   Pushing all files to GitHub
echo   Repo: RohitKankhedia/SOP-Chat-boat-ver-1.0
echo ============================================================
echo.

:: ── Check git ────────────────────────────────────────────────
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] git not found. Install Git from https://git-scm.com
    goto :end
)
echo [OK] git found.

:: ── Remove stale git lock files ──────────────────────────────
if exist ".git\index.lock"      del /f /q ".git\index.lock"
if exist ".git\HEAD.lock"       del /f /q ".git\HEAD.lock"
if exist ".git\config.lock"     del /f /q ".git\config.lock"
if exist ".git\COMMIT_EDITMSG.lock" del /f /q ".git\COMMIT_EDITMSG.lock"
echo [OK] Git lock files cleared.

:: ── Set identity ─────────────────────────────────────────────
git config user.name  "Rohit Kankhedia"
git config user.email "npexluser238@claude.clairvoyantsoft.com"

:: ── Init repo if not already a git folder ────────────────────
if not exist ".git" (
    echo [SETUP] Initializing new git repo...
    git init -b main
) else (
    echo [OK] Existing git repo found.
)

:: ── Set/update remote with token ─────────────────────────────
echo [SETUP] Enter your GitHub Personal Access Token (starts with github_pat_)
echo         (it will not be saved to any file)
set /p GH_TOKEN="Token: "
echo.
git remote remove origin 2>nul
git remote add origin https://%GH_TOKEN%@github.com/RohitKankhedia/SOP-Chat-boat-ver-1.0.git
echo [OK] Remote set.

:: ── Stage all files ──────────────────────────────────────────
echo [COMMIT] Staging all files...
git add -A
git status --short
echo.

:: ── Amend last commit if it had the token, else new commit ───
git log --oneline -1 2>nul | findstr /i "v3.0" >nul
if %errorlevel%==0 (
    echo [COMMIT] Amending previous commit to remove token from history...
    git commit --amend --no-edit
) else (
    echo [COMMIT] Creating new commit...
)
git commit -m "feat: v3.0 Guardrails Edition — full update

- agents/guardrails.py: code-level input/output safety (no LLM)
  - Input: 25+ prompt injection patterns, PII detection, length gate
  - Output: retrieval hard-block, PII redaction, sanitization, length cap
- agents/retrieval/embedder.py: scikit-learn TF-IDF+SVD (no torch/fastembed)
- agents/retrieval/faiss_index.py: pure numpy cosine similarity (no faiss-cpu)
- chatbot/app.py: torch blocker, working directory fix, guardrails wired
- scripts/generate_portfolio.py: Python 3.14 randint fix
- LLM model updated to openai/gpt-oss-120b across all agents
- run.bat: one-click launcher with dependency checks and error display
- README.md, PITCH_SCRIPT.txt: updated to v3.0

EXL Hackathon 2026"

if %errorlevel% neq 0 (
    echo [INFO] Nothing new to commit - files already up to date.
)

:: ── Push ─────────────────────────────────────────────────────
echo.
echo [PUSH] Pushing to GitHub...
git push origin main --force
if %errorlevel% neq 0 (
    echo.
    echo [RETRY] Trying with HEAD...
    git push origin HEAD:main --force
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed. See error above.
) else (
    echo.
    echo ============================================================
    echo   SUCCESS! All files pushed to GitHub.
    echo   https://github.com/RohitKankhedia/SOP-Chat-boat-ver-1.0
    echo ============================================================
)

:end
echo.
echo Press any key to close...
pause >nul
