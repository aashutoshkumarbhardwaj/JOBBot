#!/usr/bin/env python3
"""
LinkedIn Daily Digest Bot
-------------------------
Dedicated script that fetches:
1. Official LinkedIn Jobs (last 24h) via JobSpy
2. Informal LinkedIn Posts mentioning hiring (last 24h) via Google X-Ray Search

Emails a consolidated daily digest.
"""

import json
import os
import re
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
SEEN_FILE = BASE_DIR / "seen_linkedin_jobs.json"
TIMEOUT = 15

# --- SCORING LOGIC ---
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

# --- UTILS ---
def load_json(path, default):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def send_email(subject, body, to_addr, smtp_user, smtp_pass):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())

# --- SCRAPERS ---
def fetch_linkedin_jobs():
    """Scrapes official LinkedIn Jobs (past 24 hrs) via JobSpy."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("[warn] jobspy not installed.")
        return []

    print("[info] Fetching LinkedIn Jobs...")
    jobs_found = []
    search_terms = ["AI Engineer", "Machine Learning", "Data Scientist"]
    
    for term in search_terms:
        try:
            jobs_df = scrape_jobs(
                site_name=["linkedin"],
                search_term=term,
                location="India",
                results_wanted=30,
                hours_old=24
            )
            if jobs_df is not None and not jobs_df.empty:
                for _, row in jobs_df.iterrows():
                    title = str(row.get('title', 'Unknown'))
                    company = str(row.get('company', 'Unknown'))
                    url = str(row.get('job_url', ''))
                    if url and url != 'nan':
                        jobs_found.append((url, company, title, url, "Official Job"))
        except Exception as e:
            print(f"[error] Failed LinkedIn jobs for '{term}': {e}")
    return jobs_found

def fetch_linkedin_posts():
    """Uses Google X-Ray to find LinkedIn posts mentioning hiring in AI/ML (past 24 hrs)."""
    print("[info] Fetching LinkedIn Posts via Google X-Ray...")
    posts_found = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Google Dork: site:linkedin.com/posts "hiring" ("AI Engineer" OR "Machine Learning" OR "Data Scientist")
    query = 'site:linkedin.com/posts "hiring" ("AI Engineer" OR "Machine Learning" OR "Data Scientist")'
    enc_query = urllib.parse.quote(query)
    # tbs=qdr:d restricts search to the past 24 hours
    google_url = f"https://www.google.com/search?q={enc_query}&tbs=qdr:d"
    
    try:
        r = requests.get(google_url, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Google search result blocks
            for g in soup.find_all('div', class_='g'):
                a_tag = g.find('a')
                if a_tag and 'href' in a_tag.attrs:
                    url = a_tag['href']
                    if 'linkedin.com/posts' in url:
                        title_tag = g.find('h3')
                        title = title_tag.text if title_tag else "LinkedIn Post"
                        snippet_tag = g.find('div', class_='VwiC3b')
                        snippet = snippet_tag.text if snippet_tag else "Check post for details"
                        
                        posts_found.append((url, "LinkedIn Post", title, url, "Informal Post"))
    except Exception as e:
        print(f"[error] Failed Google X-Ray scrape: {e}")
        
    return posts_found

def main():
    seen = load_json(SEEN_FILE, [])
    seen_ids = set(seen)
    
    all_results = fetch_linkedin_jobs() + fetch_linkedin_posts()
    new_postings = []
    current_ids = set()

    for item_id, company, title, url, source_type in all_results:
        current_ids.add(item_id)
        if item_id not in seen_ids:
            score = get_job_score(title)
            # For informal posts, title is often just the person's name + "hiring", so we bump their score manually
            if source_type == "Informal Post":
                score = 150 # Automatically treat recent hiring posts as high value
                
            if score > 0:
                new_postings.append((score, company, title, url, source_type))

    # Update state
    seen_ids.update(current_ids)
    save_json(SEEN_FILE, list(seen_ids)[-2000:])

    if not new_postings:
        print("No new LinkedIn jobs/posts this run.")
        return

    # Sort descending
    new_postings.sort(key=lambda x: x[0], reverse=True)

    lines = [f"Found {len(new_postings)} new LinkedIn opportunities in the last 24h:\n"]
    for score, company, title, url, source_type in new_postings:
        if score == 150:
            rank = "🌟 [RANK 1]"
        elif score == 100:
            rank = "✨ [AI/ML Role]"
        elif score == 50:
            rank = "🚀 [Entry Level]"
        else:
            rank = "💻 [Tech Role]"
            
        lines.append(f"{rank} [{source_type}] {company} - {title}\n  Link: {url}\n")
        
    body = "\n".join(lines)
    subject = f"🔵 LinkedIn Daily Digest: {len(new_postings)} New Opportunities"

    to_addr = os.environ.get("ALERT_TO_EMAIL")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([to_addr, smtp_user, smtp_pass]):
        print("Email env vars not set. New postings were:")
        print(body)
        return

    send_email(subject, body, to_addr, smtp_user, smtp_pass)
    print(f"Sent LinkedIn Daily Digest to {to_addr}")

if __name__ == "__main__":
    main()
