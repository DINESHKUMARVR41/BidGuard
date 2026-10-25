# BidGuard — Tender Discovery & Pre-Bid Risk Review

BidGuard helps a business discover relevant public tender listings, rank them against a company profile, extract text from tender PDFs, and flag eligibility clauses for human review.

## What's improved in this version

- **Background discovery:** starting a TinyFish run returns immediately. It runs in a background thread, so the browser page and other API calls remain responsive while the portal is being inspected.
- **15-minute discovery cache:** repeated clicks reuse a recent successful/partial discovery instead of paying for another slow browser session. Use **Force refresh** when you actually need a new portal search.
- **Discovery progress:** the UI polls the job status and refreshes the tender list when the run completes.
- **Fast local search:** tender search and status filtering happen in SQLite, with a bounded result page.
- **Company-profile match score:** saved tenders receive a transparent heuristic relevance score with short reasons based on keywords, categories, regions and exclusions. This is a relevance estimate, not an eligibility result.
- **PDF extraction:** text-based PDFs are stored and extracted locally. Page separators are preserved in the extracted text.
- **Deduplication:** repeated tender references/URLs are not imported again for the same account.
- **Safe fallback:** manual tender entry remains available if a portal blocks automation or returns no usable results.

## Requirements

- Windows 10/11
- Python 3.11 recommended
- A Firebase Web App with Email/Password authentication enabled
- A TinyFish API key for automatic browser-based discovery

## Setup on Windows PowerShell

From the extracted `BidGuard-main` directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and verify the Firebase web configuration values. Set `TINYFISH_API_KEY` if you want automatic discovery. Then start the app:

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

### Firebase setup

In Firebase Console, enable **Authentication → Sign-in method → Email/Password**. The values `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, and `FIREBASE_APP_ID` must belong to the same Firebase Web App. The API key is client configuration, not a service-account secret; do not add service-account private keys to the frontend or commit `.env`.

## Faster discovery workflow

1. Set up a company profile once.
2. Click **Discover tenders**. The API responds quickly and the search runs in the background.
3. Continue using the app while discovery runs. The tender list updates after completion.
4. Click **Force refresh** only when you want to start a new external browser session immediately.
5. Browse and rank saved records locally without re-running TinyFish.
6. Upload PDFs and run the preliminary eligibility review only on shortlisted tenders.

The 15-minute cache applies to completed runs with a `success` or `partial` result. A run that is still active is reused instead of starting a duplicate session. Background jobs are stored in SQLite; the worker itself is an in-process thread, so keep the FastAPI process running until the job finishes. For multi-worker/production deployments, move background work to a durable queue such as Celery/RQ and a shared database.

## API endpoints

- `GET /api/health` — app health check
- `GET /api/tenders?q=...&status=...&limit=...&offset=...` — search saved tenders
- `POST /api/discovery/run` — start/reuse a discovery run
- `POST /api/discovery/run?force=true` — bypass the recent-result cache
- `GET /api/discovery/jobs/{job_id}` — poll a discovery job
- `GET /api/discovery/latest` — latest discovery job for the signed-in user
- `POST /api/tenders/manual` — add a verified tender manually
- `POST /api/tenders/{id}/documents` — upload a text-based PDF
- `POST /api/tenders/{id}/analyze` — run the local preliminary clause review

Account-specific endpoints require a valid Firebase ID token.

## Important limitations

- TinyFish still has to navigate the source website; the external search itself may take tens of seconds or minutes. Background execution improves app responsiveness but does **not** make the external portal instantly searchable.
- The portal may change its UI, restrict automation, show CAPTCHA, or provide incomplete visible results. BidGuard does not bypass access controls.
- Discovery currently uses TinyFish for portal navigation. It does not claim a direct official tender API exists.
- The company match score is keyword/rule-based and can produce false positives or misses.
- Eligibility review is currently local, heuristic and preliminary. It is not a legal opinion or an official eligibility determination. Verify the latest tender notice, all corrigenda, financial periods, exemptions, supporting documents and every important clause manually.
- Scanned PDFs need OCR, which is not included. If text extraction returns no text, review the original document manually.
- Firebase is required for sign-in. TinyFish is required for automatic discovery. Manual tender entry and local review can still be used after authentication when discovery is unavailable.
- This is a local hackathon MVP. Before public deployment, add rate limiting, robust job queueing, monitoring, retention controls, backups, HTTPS and production security review.
