<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d1b2a,50:1b263b,100:415a77&height=200&section=header&text=Job%20Alert%20Bot&fontSize=44&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Free%2C%20Serverless%20Monitoring%20for%20Greenhouse%20%26%20Lever%20Job%20Boards&descAlignY=55&descSize=17" />

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=21&duration=3000&pause=800&color=778DA9&center=true&vCenter=true&width=780&lines=Polls+Company+Career+Pages+Every+15+Minutes;Emails+You+the+Moment+a+New+Role+Goes+Live;Runs+Free+on+GitHub+Actions+%E2%80%94+No+Server+Needed;Greenhouse+%2B+Lever+Support%2C+Diffed+Against+Seen+Jobs" alt="Typing SVG" />

<br/>

[![Runs on](https://img.shields.io/badge/Runs_on-GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](#-how-it-works)
[![Schedule](https://img.shields.io/badge/Polls_every-15_minutes-415a77?style=for-the-badge&logo=clockify&logoColor=white)](#-how-it-works)
[![ATS Support](https://img.shields.io/badge/ATS-Greenhouse_%7C_Lever-778DA9?style=for-the-badge)](#-adding-companies)
[![Cost](https://img.shields.io/badge/Cost-%240%2Fmonth-2ea44f?style=for-the-badge)](#-cost--limits)

[![GitHub Repo stars](https://img.shields.io/github/stars/aashutoshkumarbhardwaj/job-alert-bot?style=social)](https://github.com/aashutoshkumarbhardwaj/job-alert-bot)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](#-license)

</div>

<br/>

## 🎯 Overview

**Job Alert Bot** watches your target companies' career pages and emails you the second a new role is posted — no polling by hand, no missed postings, no paid scraping service. It runs entirely on **GitHub Actions' free tier**, checking every **15 minutes**, and supports companies hosted on **Greenhouse** and **Lever** — the two most common ATS platforms for startups and mid-size companies.

<br/>

## ⚙️ How It Works

```text
companies.json
       │
       ▼
┌─────────────────────────┐
│        monitor.py        │
│                           │
│  fetch open roles from   │
│  each company's ATS API  │
└─────────────┬─────────────┘
              │
              ▼
   diff against seen_jobs.json
              │
       ┌──────┴──────┐
       ▼             ▼
  no new roles   new roles found
       │             │
     (exit)     email via SMTP
                      │
                      ▼
              update seen_jobs.json
```

| File | Role |
|---|---|
| `companies.json` | Your target company list (name, ATS type, slug) |
| `monitor.py` | Fetches jobs, diffs against `seen_jobs.json`, emails anything new |
| `.github/workflows/job-alerts.yml` | Runs the check every 15 minutes on GitHub's free Actions runners |

<br/>

## 🚀 Setup (5–10 min)

<br/>

### 1️⃣ Create a GitHub repo

Push this folder to a **new private** repo. Keep it private — your email ends up in Action logs otherwise, and there's no upside to making it public.

```bash
cd job-alert-bot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/job-alert-bot.git
git push -u origin main
```

<br/>

### 2️⃣ Set up a Gmail App Password

Regular Gmail passwords don't work with SMTP anymore — you need an App Password:

1. Enable **2-Step Verification** on your Google Account (Security tab)
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create an app password for **"Mail"** → copy the 16-character code

<br/>

### 3️⃣ Add GitHub Secrets

`Repo → Settings → Secrets and variables → Actions → New repository secret`

| Secret name | Value |
|---|---|
| `SMTP_USER` | Your Gmail address (the sender) |
| `SMTP_PASS` | The 16-character app password from step 2 |
| `ALERT_TO_EMAIL` | Where alerts should land (can equal `SMTP_USER`) |

<br/>

### 4️⃣ Edit `companies.json`

Replace the example entries with your real target list. You need each company's ATS **slug**:

| ATS | Careers URL pattern | Example |
|---|---|---|
| **Greenhouse** | `boards.greenhouse.io/<slug>` | `boards.greenhouse.io/stripe` → slug is `stripe` |
| **Lever** | `jobs.lever.co/<slug>` | `jobs.lever.co/notion` → slug is `notion` |

```json
[
  { "name": "CompanyName", "ats": "greenhouse", "slug": "companyname" },
  { "name": "OtherCompany", "ats": "lever", "slug": "othercompany" }
]
```

> Not every company uses Greenhouse or Lever — some use Workday, Ashby, SmartRecruiters, etc. This bot currently supports **Greenhouse and Lever only**. Extending to more ATS platforms is possible if needed for specific target companies.

Commit and push the change.

<br/>

### 5️⃣ Test it manually

`Repo → Actions tab → Job Alert Bot → Run workflow`

Check the logs to confirm it ran and see what jobs were found. **The first run treats every currently-open job as "already seen"** — so you won't get flooded with existing postings. Only genuinely new roles after that trigger an email.

<br/>

### 6️⃣ Done

It now runs automatically, every 15 minutes, for free.

<br/>

## 💸 Cost & Limits

| | |
|---|---|
| GitHub Actions free tier | 2,000 min/month (private repos) |
| Cost per run | ~1 minute |
| Runs/day at 15-min interval | 96 |
| Worst-case usage | ~96 min/day → well within free tier for a modest company list |

> ⚠️ If you add a lot of companies, keep an eye on your Actions usage — more companies per run means each run takes slightly longer.

<br/>

## 🔍 Finding a Company's ATS

Visit the company's careers page — the URL itself, or a quick look at page source / network requests, usually reveals `boards.greenhouse.io` or `jobs.lever.co` if they use one of the supported platforms.

<br/>

## 🚫 What This Doesn't Do

**LinkedIn / X monitoring** is intentionally left out. Neither platform offers a public API for this without paid scraping infrastructure or violating their Terms of Service. LinkedIn's own native job alerts remain the more reliable and compliant way to cover that surface — use them alongside this bot rather than instead of it.

<br/>

## 📁 Repository Structure

```text
job-alert-bot/
├── .github/
│   └── workflows/
│       └── job-alerts.yml    # scheduled GitHub Actions workflow
├── companies.json             # target company list
├── monitor.py                  # fetch → diff → email
├── seen_jobs.json              # state file, auto-updated each run
└── requirements.txt
```

<br/>

## 📄 License

Released under the **MIT** License.

<br/>

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:415a77,50:1b263b,100:0d1b2a&height=100&section=footer" />

**If this is useful to you, consider ⭐ starring the repo.**

</div>
