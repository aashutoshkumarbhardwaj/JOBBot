#!/usr/bin/env python3
"""
Twitter/X Daily Digest Bot
--------------------------
Dedicated script that fetches informal Twitter posts mentioning hiring
or internships (last 24h) via Google X-Ray Search.

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
SEEN_FILE = BASE_DIR / "seen_twitter_jobs.json"
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

REJECT_KEYWORDS = [
    "senior", "lead", "manager", "staff", "director", "head", "principal", "yoe", 
    "years of experience", "experienced", "1+", "2+", "3+", "4+", "5+", "vp", "president", "architect"
]

OTHER_TECH_KEYWORDS = [
    "software", "dev", "developer", "engineer", "engineering", "fullstack", "full-stack", "full stack", "backend", "back-end", "back end"
]

def get_job_score(title, description=""):
    title_lower = title.lower()
    desc_lower = description.lower()
    
    for kw in REJECT_KEYWORDS:
        if kw in title_lower:
            return 0
            
    if description:
        # Strictly reject any description asking for 1+ years of experience (ignoring 0-1, 0-2)
        yoe_regex = r'(?<!0-)(?<!0 -)(?<!0 to )\b([1-9]|1[0-9])\+?\s*(?:years|yrs?)\b'
        yoe_pattern1 = yoe_regex + r'.{0,40}(?:experience|yoe|working|hands-on|proven)'
        yoe_pattern2 = r'(?:experience|yoe|requirements?).{0,40}' + yoe_regex
        
        if re.search(yoe_pattern1, desc_lower) or re.search(yoe_pattern2, desc_lower):
            return 0
            
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
def fetch_twitter_posts():
    """Uses DuckDuckGo HTML to find Twitter/X posts mentioning hiring or internships in AI/ML."""
    print("[info] Fetching Twitter Posts via DuckDuckGo HTML...")
    posts_found = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # DuckDuckGo query (same dork, but no time filter needed as DDG relies on our local deduplication anyway)
    query = '(site:x.com OR site:twitter.com) ("hiring" OR "internship" OR "fresher" OR "freshers") ("AI Engineer" OR "Machine Learning" OR "Data Scientist")'
    enc_query = urllib.parse.quote(query)
    
    # DuckDuckGo HTML endpoint avoids JS challenges and CAPTCHAs common on GitHub Action IPs
    ddg_url = f"https://html.duckduckgo.com/html/?q={enc_query}"
    
    try:
        r = requests.get(ddg_url, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # DuckDuckGo HTML results are typically in div.result
            for result in soup.find_all('div', class_='result'):
                a_url = result.find('a', class_='result__url')
                a_snippet = result.find('a', class_='result__snippet')
                
                if a_url and 'href' in a_url.attrs:
                    url = a_url['href']
                    
                    if 'x.com/' in url or 'twitter.com/' in url:
                        # DDG direct link or wrapped link
                        if url.startswith('//duckduckgo.com/l/?uddg='):
                            parsed = urllib.parse.urlparse('https:' + url)
                            url = urllib.parse.unquote(urllib.parse.parse_qs(parsed.query).get('uddg', [url])[0])
                            
                        # Try to get title from snippet or a tag
                        title = "Twitter Post"
                        snippet_text = a_snippet.get_text(strip=True) if a_snippet else "Check tweet for details"
                        
                        posts_found.append((url, "X / Twitter", title, url, snippet_text))
    except Exception as e:
        print(f"[error] Failed DuckDuckGo scrape: {e}")
        
    return posts_found

def main():
    seen = load_json(SEEN_FILE, [])
    seen_ids = set(seen)
    
    all_results = fetch_twitter_posts()
    new_postings = []
    current_ids = set()

    for item_id, company, title, url, snippet in all_results:
        current_ids.add(item_id)
        if item_id not in seen_ids:
            score = get_job_score(title, snippet)
            
            # If score is 0, it means it hit a REJECT_KEYWORD. 
            # If it didn't hit a reject keyword, bump it to 150 because it matched our Google Dork for hiring.
            if score != 0:
                score = 150 
                new_postings.append((score, company, title, url, snippet))

    # Update state
    seen_ids.update(current_ids)
    save_json(SEEN_FILE, list(seen_ids)[-2000:])

    if not new_postings:
        print("No new Twitter jobs/posts this run.")
        return

    # Sort descending
    new_postings.sort(key=lambda x: x[0], reverse=True)

    lines = [f"Found {len(new_postings)} new Twitter/X opportunities in the last 24h:\n"]
    for score, company, title, url, snippet in new_postings:
        rank = "🌟 [RANK 1: Direct Tweet]"
        lines.append(f"{rank} {title}\n  Snippet: {snippet}\n  Link: {url}\n")
        
    body = "\n".join(lines)
    subject = f"🐦 Twitter Daily Digest: {len(new_postings)} New Opportunities"

    to_addr = os.environ.get("ALERT_TO_EMAIL")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([to_addr, smtp_user, smtp_pass]):
        print("Email env vars not set. New postings were:")
        print(body)
        return

    send_email(subject, body, to_addr, smtp_user, smtp_pass)
    print(f"Sent Twitter Daily Digest to {to_addr}")

if __name__ == "__main__":
    main()
