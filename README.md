# Job Alert Bot

Polls company job boards every 15 minutes and emails you the moment a new role is posted.
Supports **Greenhouse** and **Lever**-hosted boards (covers most startups and a lot of mid-size companies).

## How it works
- `companies.json` — your target list
- `monitor.py` — fetches jobs, diffs against `seen_jobs.json`, emails new ones
- `.github/workflows/job-alerts.yml` — runs it every 15 min on GitHub's free Actions runners, no server needed

## Setup (5–10 min)

### 1. Create a GitHub repo
Push this folder to a new **private** GitHub repo (private matters since your email address ends up in Action logs otherwise minimal, but keep it private regardless).

```bash
cd job-alert-bot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/job-alert-bot.git
git push -u origin main
```

### 2. Set up a Gmail App Password (for sending alerts)
Regular Gmail passwords won't work with SMTP anymore. You need an App Password:
1. Go to your Google Account → Security → 2-Step Verification (must be enabled)
2. Go to **myaccount.google.com/apppasswords**
3. Create an app password for "Mail" — copy the 16-character code

### 3. Add GitHub Secrets
In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:
| Secret name | Value |
|---|---|
| `SMTP_USER` | your Gmail address (this sends the email) |
| `SMTP_PASS` | the 16-character app password from step 2 |
| `ALERT_TO_EMAIL` | the email address you want alerts sent to (can be same as SMTP_USER) |

### 4. Edit `companies.json` with your real target companies
Replace the example entries. You need each company's **ATS slug**:

**Greenhouse companies** — find the slug from their careers URL:
`boards.greenhouse.io/<slug>` → e.g. `boards.greenhouse.io/stripe` → slug is `stripe`

**Lever companies** — same idea:
`jobs.lever.co/<slug>` → e.g. `jobs.lever.co/notion` → slug is `notion`

Not every company uses Greenhouse or Lever — some use Workday, Ashby, SmartRecruiters, etc. This bot currently supports Greenhouse and Lever only (the two most common for startups). Tell me your target companies and I can extend it to more ATS platforms if needed.

```json
[
  { "name": "CompanyName", "ats": "greenhouse", "slug": "companyname" },
  { "name": "OtherCompany", "ats": "lever", "slug": "othercompany" }
]
```

Commit and push this change.

### 5. Test it manually
Go to your repo → **Actions** tab → **Job Alert Bot** → **Run workflow**. Check the logs to confirm it ran and see if any jobs were found. The *first* run will treat all currently open jobs as "already seen" (so you won't get spammed with everything that's already posted) — only genuinely new postings after that will trigger an email.

### 6. Done
It now runs automatically every 15 minutes for free (GitHub Actions free tier gives 2,000 min/month, this uses ~1 min per run ≈ 96 min/day worst case — well within limits for a private repo... actually check your usage if you add many companies).

## Notes
- To find out if a company uses Greenhouse or Lever, visit their careers page — the URL or page source usually reveals it (`boards.greenhouse.io` or `jobs.lever.co` in network requests / page links).
- Want LinkedIn/X monitoring too? Those don't have public APIs for this without paid scraping infra or violating ToS, so I intentionally left them out — LinkedIn's native job alerts (which you already set up) are the more reliable and compliant way to get those.
