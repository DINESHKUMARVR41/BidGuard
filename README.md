# BidGuard MVP

A local-first tender discovery and preliminary eligibility review app.

## Features
- Company profile saved in SQLite
- Optional TinyFish tender discovery integration
- Manual tender URL entry fallback
- PDF upload and text extraction
- Rule-based requirement detection and preliminary profile comparison
- Source links, retrieval timestamps, risk status and next-action checklist
- Responsive dashboard

## Run on Windows PowerShell
```powershell
cd path\to\BidGuard
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

If activation is blocked:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## TinyFish
Add your API key to `.env` as `TINYFISH_API_KEY=...`, then restart the app. The integration uses the TinyFish Python SDK's documented Agent streaming pattern. API access, account credits and the exact response schema must be validated against your current account/docs. If discovery is blocked or fails, the app reports the problem rather than fabricating tenders.

## Limitations
- Public procurement portals can use CAPTCHA or restrict automation. BidGuard does not bypass access controls.
- The built-in parser is a baseline heuristic, not legal advice or an official eligibility determination.
- OCR for scanned PDFs is not included.
- The app does not submit bids or guarantee eligibility.
