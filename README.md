# BidGuard — Firebase authentication + personalized tender discovery

## Included
- Firebase Email/Password authentication for registration and sign-in.
- Firebase ID token verification on the FastAPI backend before account-specific endpoints are served.
- Company registration and profile storage in SQLite, scoped to the signed-in Firebase user.
- Profile-based tender discovery goal using company industry, products/services, locations, categories, keywords, exclusions and preferred value range.
- Tender PDF text extraction and preliminary eligibility review.

## 1. Configure Firebase (required)

An API key by itself is not the complete Firebase Web App configuration. In the [Firebase Console](https://console.firebase.google.com/):

1. Open or create your Firebase project.
2. Go to **Authentication → Sign-in method** and enable **Email/Password**.
3. Go to **Project settings → General → Your apps**. Register a Web app if you do not already have one.
4. Copy these four values from the Web App configuration: `apiKey`, `authDomain`, `projectId`, and `appId`.
5. Copy `.env.example` to `.env`. The provided example is prefilled for project `project-eb845`; confirm it matches your Firebase Web App configuration before running. Keep `FIREBASE_PROJECT_ID` exactly the same as the Firebase project ID.

The Firebase Web API key is a client configuration value, not a private server credential. You should still restrict it appropriately in Google Cloud. Never put a Firebase service-account private key in the frontend or commit `.env` to GitHub.

## 2. Run on Windows PowerShell

Extract the ZIP, open PowerShell in the extracted `BidGuard-main` folder, then run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env now and fill the Firebase values (and TINYFISH_API_KEY if available)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Create a Firebase account, enter your company details, then run tender discovery.

If PowerShell says `.env` already exists, do not overwrite your existing configuration; edit it manually instead. Ensure the four `FIREBASE_*` values match project `project-eb845`, then restart the server after changing `.env`.

## 3. TinyFish

Add `TINYFISH_API_KEY=your_key` to `.env`, restart the server and use Discover tenders. The integration depends on current TinyFish SDK compatibility, account access, and whether the portal permits public automated navigation. No tenders are fabricated when retrieval fails.

## Database notes

Company profiles and tenders are stored locally in SQLite. The app can add the Firebase UID column to a newer existing users table, but the older shared-profile/tender schema is not automatically migrated. If upgrading from an older BidGuard version, back up your database first. If you do not need the old data, rename the old `bidguard.db` before starting this version so the new schema is created cleanly.

## Security and limitations

- Firebase handles password storage and sign-in; BidGuard verifies Firebase ID tokens server-side.
- Email/password sign-in must be enabled in Firebase Console (Authentication → Sign-in method → Email/Password). If Firebase returns `auth/configuration-not-found`, first finish setting up Firebase Authentication and enable this provider; check that the app uses the same project ID and Web API key. Email verification and password-reset UI are not implemented in BidGuard yet.
- This is a local MVP, not a production deployment. Use HTTPS, review Firebase API key restrictions, add rate limiting and operational monitoring before public deployment.
- PDF extraction supports text-based PDFs, not OCR for scanned documents.
- Tender analysis is heuristic and preliminary, not legal advice or an official eligibility determination.
