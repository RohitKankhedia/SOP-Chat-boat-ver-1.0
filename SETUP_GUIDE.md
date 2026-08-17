# Setup & Run Guide
## Agentic Rate Change Intelligence System v3.0

---

## What You Need Before Starting

### 1. Python
- **Required:** Python 3.11, 3.12, 3.13, or 3.14
- **On EXL sandbox:** Already installed at `C:\Users\vmuser\AppData\Local\Programs\Python\Python314\`
- **Check:** Open PowerShell and run `python --version`
- **Download if missing:** https://python.org/downloads

### 2. Groq API Key (free)
- Go to https://console.groq.com
- Sign in or create a free account
- Click **API Keys** → **Create API Key**
- Copy the key — it starts with `gsk_`
- You will be asked to paste it when you run the app

### 3. Internet connection
- Needed only for the Groq API (LLM calls)
- All other packages are installed locally
- No ML model downloads required

### 4. Git (for GitHub push only)
- Only needed if you want to push to GitHub
- Already installed on EXL sandbox
- Download: https://git-scm.com

---

## Python Packages Required

These are installed automatically by `run.bat`. Listed here for reference:

| Package | Purpose | Size |
|---|---|---|
| `streamlit` | Web UI framework | ~30MB |
| `groq` | LLM API client | ~1MB |
| `pandas` | Data processing | ~20MB |
| `scikit-learn` | TF-IDF + SVD embeddings | ~25MB |
| `numpy` | Vector math (comes with scikit-learn) | included |
| `rank-bm25` | Keyword search | ~0.1MB |
| `pdfplumber` | PDF document parsing | ~5MB |
| `python-docx` | Word document parsing | ~2MB |

**Total download:** ~85MB (one-time, cached after first install)

**Not required (removed):**
- ~~torch / PyTorch~~ — incompatible with Python 3.14 on Windows
- ~~sentence-transformers~~ — requires torch
- ~~fastembed~~ — requires large ONNX model downloads (blocked on sandbox)
- ~~faiss-cpu~~ — replaced with numpy

---

## Quickest Way to Run — One Click

1. Open `C:\Users\vmuser\Claude\Projects\SOP Chat bot\` in Windows Explorer
2. Double-click **`run.bat`**
3. When asked, paste your Groq API key
4. Wait ~15 seconds for first-run index build
5. Browser opens at **http://localhost:8501**

The bat file handles everything: dependency checks, data generation, cache cleanup, and app launch. If anything fails, the window stays open showing the error.

---

## Manual Setup (if bat file doesn't work)

Open PowerShell and run each block in order:

### Step 1 — Go to project folder
```powershell
cd "C:\Users\vmuser\Claude\Projects\SOP Chat bot"
```

### Step 2 — Install packages
```powershell
& "C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe" -m pip install `
  streamlit groq pandas scikit-learn rank-bm25 pdfplumber python-docx `
  --break-system-packages
```

### Step 3 — Generate data files
```powershell
& "C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe" scripts\generate_portfolio.py
& "C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe" scripts\create_sops.py
```

### Step 4 — Set your API key
```powershell
$env:GROQ_API_KEY = "gsk_your-key-here"
```

### Step 5 — Run the app
```powershell
& "C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe" -m streamlit run chatbot/app.py
```

Open **http://localhost:8501** in your browser.

---

## Files Created at Runtime (auto-generated, not in git)

| File | Created by | Purpose |
|---|---|---|
| `data/loan_portfolio.csv` | `scripts/generate_portfolio.py` | 500 synthetic customer records |
| `data/competitor_rates.csv` | `scripts/generate_portfolio.py` | 3 competitor bank rates |
| `data/SOP_*.docx` | `scripts/create_sops.py` | 5 SOP Word documents |
| `data/sop_vectors.npy` | App on first run | Embedding matrix (numpy) |
| `data/sop_vectorizer.pkl` | App on first run | Fitted TF-IDF pipeline |
| `data/sop_chunks.json` | App on first run | Chunk metadata |
| `data/sop_bm25.pkl` | App on first run | BM25 keyword index |

These are excluded from git (`.gitignore`) and rebuilt automatically whenever SOP files change.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Your Groq API key (`gsk_...`). Get free at https://console.groq.com |

Set it in PowerShell: `$env:GROQ_API_KEY = "gsk_your-key-here"`
Set it permanently: Windows → System Properties → Environment Variables

---

## Troubleshooting

### "DLL initialization failed" / torch error
The torch blocker in `app.py` should prevent this. If it still appears:
- Clear `__pycache__`: delete all `__pycache__` folders in the project
- Run `run.bat` which does this automatically

### "FileNotFoundError: data\loan_portfolio.csv"
The app sets its working directory automatically. If this still appears:
- Make sure you're running from the project root (where `chatbot/` and `agents/` folders are)
- Run `run.bat` — it calls `generate_portfolio.py` every time

### "GROQ_API_KEY not set"
- The bat file will ask for it interactively
- Or set it manually: `$env:GROQ_API_KEY = "gsk_..."`

### App loads but LLM responses fail
- Check your Groq API key is valid at https://console.groq.com
- Check the model name: `openai/gpt-oss-120b` (set in each agent file under `MODEL = ...`)

### "No SOP files found" / empty chatbot answers
- Run `scripts\create_sops.py` to regenerate the SOP documents
- Check that `.docx` files exist in the `data/` folder

### Index rebuilds every time
- The index is stale if SOP files are newer than index files
- This is normal after `create_sops.py` runs
- After first successful build, subsequent starts load from cache (~1 second)

---

## How to Stop the App

Press **Ctrl+C** in the terminal window running Streamlit.

---

## Supported Browsers

Chrome, Firefox, Edge — any modern browser. The app runs on `http://localhost:8501`.
