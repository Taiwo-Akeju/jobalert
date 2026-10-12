#!/usr/bin/env python3
"""Daily job alert: English-language IT roles in Germany -> email.

Sources: Arbeitnow (no key needed) and Adzuna (free key, optional).
Env vars: GMAIL_USER, GMAIL_APP_PASSWORD, TO_EMAIL, [ADZUNA_APP_ID, ADZUNA_APP_KEY]
"""
import os, re, time, html, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

TO_EMAIL = os.environ.get("TO_EMAIL", "akeju.taiwo5@gmail.com")
LOOKBACK_HOURS = 26  # a little over a day so nothing slips through

TITLE_KEYWORDS = [
    "devops", "it administrator", "systems administrator", "system administrator",
    "sysadmin", "systems engineer", "system engineer", "cloud engineer",
    "linux engineer", "linux administrator", "linux", "it specialist",
    "azure", "site reliability", "sre", "platform engineer",
]
ADZUNA_QUERIES = [
    "devops engineer", "senior it administrator", "systems engineer",
    "senior systems engineer", "cloud engineer", "linux engineer",
    "linux administrator", "it specialist", "azure engineer",
]

EN = set("the and with you we our experience team will of to for are is in a skills work".split())
DE = set("und der die das mit wir sie für ein eine erfahrung bei zu von ist sind deine ihre".split())


def looks_english(text: str) -> bool:
    words = re.findall(r"[a-zäöüß]+", text.lower())[:300]
    en = sum(w in EN for w in words)
    de = sum(w in DE for w in words)
    return en > de


def title_matches(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in TITLE_KEYWORDS)


def fetch_arbeitnow(cutoff):
    jobs = []
    for page in range(1, 6):
        try:
            r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                             params={"page": page}, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", [])
        except Exception as e:
            print("Arbeitnow error:", e)
            break
        for j in data:
            if j.get("created_at", 0) < cutoff:
                continue
            if not title_matches(j["title"]):
                continue
            if not looks_english(j["title"] + " " + j.get("description", "")):
                continue
            jobs.append({"title": j["title"], "company": j["company_name"],
                         "location": j.get("location", ""), "url": j["url"],
                         "source": "Arbeitnow"})
    return jobs


def fetch_adzuna():
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        return []
    jobs = []
    for q in ADZUNA_QUERIES:
        try:
            r = requests.get(
                "https://api.adzuna.com/v1/api/jobs/de/search/1",
                params={"app_id": app_id, "app_key": app_key, "what": q,
                        "max_days_old": 1, "results_per_page": 50,
                        "content-type": "application/json"}, timeout=30)
            r.raise_for_status()
            for j in r.json().get("results", []):
                if not looks_english(j["title"] + " " + j.get("description", "")):
                    continue
                jobs.append({"title": j["title"],
                             "company": j.get("company", {}).get("display_name", ""),
                             "location": j.get("location", {}).get("display_name", ""),
                             "url": j["redirect_url"], "source": "Adzuna"})
        except Exception as e:
            print(f"Adzuna error for '{q}':", e)
        time.sleep(1)
    return jobs


def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def build_email(jobs):
    if not jobs:
        body = "<p>No new matching English-language jobs found today.</p>"
    else:
        rows = "".join(
            f'<li><a href="{html.escape(j["url"])}"><b>{html.escape(j["title"])}</b></a>'
            f' &ndash; {html.escape(j["company"])}, {html.escape(j["location"])}'
            f' <small>({j["source"]})</small></li>' for j in jobs)
        body = f"<p>{len(jobs)} new jobs:</p><ul>{rows}</ul>"
    return body


def send(body, count):
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Germany IT Jobs (English): {count} new"
    msg["From"], msg["To"] = user, TO_EMAIL
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.sendmail(user, [TO_EMAIL], msg.as_string())


if __name__ == "__main__":
    cutoff = time.time() - LOOKBACK_HOURS * 3600
    jobs = dedupe(fetch_arbeitnow(cutoff) + fetch_adzuna())
    print(f"Found {len(jobs)} jobs")
    send(build_email(jobs), len(jobs))
