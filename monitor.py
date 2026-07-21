#!/usr/bin/env python3
"""
Job Alert Bot
-------------
Polls each company's job board (Greenhouse or Lever) for new postings,
compares against previously seen job IDs, and emails you when something new shows up.

Run this on a schedule (see .github/workflows/job-alerts.yml) — every run:
  1. Loads companies.json (your target list)
  2. Fetches current open jobs for each company
  3. Diffs against seen_jobs.json (persisted state)
  4. Emails a summary of NEW jobs only
  5. Updates seen_jobs.json
"""

import json
import os
import re
import smtplib
import sys
import urllib.parse
from email.mime.text import MIMEText
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
COMPANIES_FILE = BASE_DIR / "companies.json"
SEEN_FILE = BASE_DIR / "seen_jobs.json"

TIMEOUT = 15

AI_KEYWORDS = [
    "applied ai", "applied scientist", "research engineer", "ai engineer", "ml engineer", 
    "machine learning", "artificial intelligence", "genai", "generative ai", "llm", 
    "large language models", "foundation models", "prompt engineer", "prompt developer", 
    "ai solutions engineer", "ai consultant", "ai specialist", "ai architect", "ai developer", 
    "machine learning scientist", "research scientist", "ai research scientist", "deep learning", 
    "computer vision", "nlp", "natural language processing", "speech ai", "multimodal", 
    "vision language model", "vlm", "rag", "retrieval augmented generation", "agentic ai", 
    "ai agents", "autonomous agents", "data scientist", "decision scientist", "analytics engineer", 
    "business intelligence", "data analyst", "data engineer", "big data", "etl", "spark", 
    "pyspark", "mlops", "model deployment", "model serving", "feature store", "inference"
]

ENTRY_LEVEL_KEYWORDS = [
    "entry level", "entry-level", "junior", "jr", "associate", "fresher", "graduate", "grad", 
    "intern", "internship", "0-1", "0-2", "0-3", "early career", "student", "month"
]

OTHER_TECH_KEYWORDS = [
    "software", "dev", "developer", "engineer", "engineering", "fullstack", "full-stack", "full stack", "backend", "back-end", "back end"
]

def get_job_score(title):
    title_lower = title.lower()
    
    is_ai = False
    for kw in AI_KEYWORDS:
        if len(kw) <= 3:
            if re.search(rf'\b{re.escape(kw)}\b', title_lower):
                is_ai = True
                break
        else:
            if kw in title_lower:
                is_ai = True
                break
                
    is_entry = False
    for kw in ENTRY_LEVEL_KEYWORDS:
        if len(kw) <= 2:
            if re.search(rf'\b{re.escape(kw)}\b', title_lower):
                is_entry = True
                break
        else:
            if kw in title_lower:
                is_entry = True
                break
                
    is_other = False
    for kw in OTHER_TECH_KEYWORDS:
        if len(kw) <= 3:
            if re.search(rf'\b{re.escape(kw)}\b', title_lower):
                is_other = True
                break
        else:
            if kw in title_lower:
                is_other = True
                break
                
    score = 0
    if is_ai and is_entry:
        score = 150
    elif is_ai:
        score = 100
    elif is_other and is_entry:
        score = 50
    elif is_other:
        score = 10
        
    return score


def load_json(path, default):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def fetch_greenhouse(slug):
    """Returns list of (job_id, title, url) for a Greenhouse-hosted board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    return [
        (str(j["id"]), j["title"], j.get("absolute_url", ""))
        for j in jobs
    ]


def fetch_lever(slug):
    """Returns list of (job_id, title, url) for a Lever-hosted board."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = r.json()
    return [
        (j["id"], j.get("text", "Untitled role"), j.get("hostedUrl", ""))
        for j in jobs
    ]


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
}


def fetch_aggregated_jobs():
    """Scrapes external job boards using JobSpy."""
    try:
        from jobspy import scrape_jobs
        import pandas as pd
    except ImportError:
        print("[warn] jobspy or pandas not installed. Skipping external scraping.")
        return []

    print("[info] Starting external job board scrape via JobSpy...")
    jobs_found = []
    
    search_terms = ["AI Engineer", "Machine Learning"]
    
    for term in search_terms:
        try:
            print(f"[info] Scraping jobs for '{term}'...")
            jobs_df = scrape_jobs(
                site_name=["indeed", "linkedin", "glassdoor"],
                search_term=term,
                location="India",
                results_wanted=30,
                hours_old=72,  # Last 3 days
                country_indeed='India'
            )
            
            if jobs_df is not None and not jobs_df.empty:
                for _, row in jobs_df.iterrows():
                    title = str(row.get('title', 'Unknown'))
                    company = str(row.get('company', 'Unknown'))
                    url = str(row.get('job_url', ''))
                    if not url or url == 'nan':
                        continue
                    jobs_found.append((url, company, title, url))
        except Exception as e:
            print(f"[error] Failed scraping for term '{term}': {e}")
            
    return jobs_found


def fetch_custom_portals():
    """Lightweight custom scraper for additional Indian portals (e.g. Instahyre) using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[warn] beautifulsoup4 not installed. Skipping custom portal scraping.")
        return []

    print("[info] Starting custom job board scrape (Instahyre)...")
    jobs_found = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    urls = [
        "https://www.instahyre.com/jobs-for-machine-learning/",
        "https://www.instahyre.com/jobs-for-artificial-intelligence/"
    ]
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                job_blocks = soup.find_all('div', class_='opportunity-info')
                if not job_blocks:
                    job_blocks = soup.find_all('div', class_='job-info')
                    
                for job in job_blocks:
                    title_elem = job.find('span', class_='opp-title') or job.find('div', class_='job-title') or job.find('a', id=lambda x: x and x.startswith('job-title'))
                    company_elem = job.find('span', class_='employer-name') or job.find('div', class_='employer-name')
                    
                    if title_elem and company_elem:
                        title = title_elem.text.strip()
                        company = company_elem.text.strip()
                        job_id = f"instahyre_{company}_{title}"
                        job_url = "https://www.instahyre.com/jobs-for-artificial-intelligence/"
                        jobs_found.append((job_id, company, title, job_url))
        except Exception as e:
            print(f"[error] Failed scraping custom portal {url}: {e}")
            
    return jobs_found


def send_email(subject, body, to_addr, smtp_user, smtp_pass):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())


def main():
    companies = load_json(COMPANIES_FILE, [])
    if not companies:
        print("No companies configured in companies.json. Nothing to do.")
        return

    seen = load_json(SEEN_FILE, {})
    new_postings = []  # list of (company_name, title, url)

    for company in companies:
        name = company["name"]
        ats = company["ats"]
        slug = company.get("slug")

        fetcher = FETCHERS.get(ats)
        if not fetcher or not slug:
            print(f"[skip] Unknown ATS '{ats}' or missing slug for {name}")
            continue

        try:
            jobs = fetcher(slug)
        except Exception as e:
            print(f"[error] Failed to fetch {name} ({ats}/{slug}): {e}")
            continue

        seen_ids = set(seen.get(name, []))
        current_ids = set()

        for job_id, title, url in jobs:
            current_ids.add(job_id)
            if job_id not in seen_ids:
                score = get_job_score(title)
                if score > 0:
                    new_postings.append((score, name, title, url))

        # Update seen list for this company to the current snapshot
        seen[name] = list(current_ids)
        print(f"[ok] {name}: {len(jobs)} open jobs, {len(current_ids - seen_ids)} new")

    # --- Execute JobSpy External Scrape ---
    scraped_jobs = fetch_aggregated_jobs()
    scraped_jobs.extend(fetch_custom_portals())
    seen_scraped_ids = set(seen.get("_SCRAPED_JOBS", []))
    current_scraped_ids = set()

    for job_id, company_name, title, url in scraped_jobs:
        current_scraped_ids.add(job_id)
        if job_id not in seen_scraped_ids:
            score = get_job_score(title)
            if score > 0:
                new_postings.append((score, company_name, title, url))
                
    seen_scraped_ids.update(current_scraped_ids)
    seen["_SCRAPED_JOBS"] = list(seen_scraped_ids)[-2000:]

    save_json(SEEN_FILE, seen)

    if not new_postings:
        print("No new postings this run.")
        return

    # Build email
    # Sort new postings by score descending
    new_postings.sort(key=lambda x: x[0], reverse=True)

    lines = [f"{len(new_postings)} new job posting(s) found (Sorted by Preference):\n"]
    for score, company_name, title, url in new_postings:
        if score == 150:
            rank_label = "🌟 [RANK 1: AI/ML Entry Level]"
        elif score == 100:
            rank_label = "✨ [AI/ML Role]"
        elif score == 50:
            rank_label = "🚀 [Entry Level Tech]"
        else:
            rank_label = "💻 [Tech Role]"

        comp_enc = urllib.parse.quote(company_name)
        portals = "(site:naukri.com OR site:linkedin.com OR site:indeed.com OR site:cutshort.io OR site:hirist.tech OR site:apna.co OR site:instahyre.com OR site:foundit.in)"
        job_enc = urllib.parse.quote(f"{company_name} {title} {portals}")
        # tbs=qdr:w (past week), sbd:1 (sort by date)
        google_link = f"https://www.google.com/search?q={job_enc}&tbs=qdr:w,sbd:1"
        # f_TPR=r604800 (past week), sortBy=DD (sort by date)
        linkedin_link = f"https://www.linkedin.com/jobs/search/?keywords={comp_enc}&f_TPR=r604800&sortBy=DD"
        lines.append(f"{rank_label}\n• [{company_name}] {title}\n  Apply: {url}\n  Google (Latest): {google_link}\n  LinkedIn (Latest): {linkedin_link}\n")
    body = "\n".join(lines)
    subject = f"🔔 {len(new_postings)} new job alert(s)"

    to_addr = os.environ.get("ALERT_TO_EMAIL")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([to_addr, smtp_user, smtp_pass]):
        print("Email env vars not set — skipping email send. New postings were:")
        print(body)
        return

    send_email(subject, body, to_addr, smtp_user, smtp_pass)
    print(f"Emailed {len(new_postings)} new posting(s) to {to_addr}")


if __name__ == "__main__":
    main()
