#!/usr/bin/env python3
"""Daily job alert: English-language IT roles in Germany -> email.
NRW jobs are listed first, other German cities below.

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

NRW_PLACES = [
    "nordrhein-westfalen", "north rhine", "nrw", "düsseldorf", "dusseldorf",
    "köln", "koeln", "cologne", "dortmund", "essen", "duisburg", "bochum",
    "wuppertal", "bielefeld", "bonn", "münster", "munster", "gelsenkirchen",
    "mönchengladbach", "aachen", "krefeld", "oberhausen", "hagen", "hamm",
    "leverkusen", "neuss", "solingen", "paderborn", "bottrop", "recklinghausen",
    "remscheid", "siegen", "gütersloh", "ratingen", "bergisch gladbach", "moers",
    "herne", "mülheim", "witten", "iserlohn", "marl", "lünen", "hürth",
    "troisdorf", "minden", "detmold",
]

EN = set("the and with you we our experience team will of to for are is in a skills work".split())
DE = set("und der die das mit wir sie für ein eine erfahrung bei zu von ist sind deine ihre".split())


def looks_english(text: str) -> bool:
    words = re.findall(r"[a-zäöüß]+", text.lower())[:300]
    en = sum(w in EN for w in words)
    de = sum(w in DE for w in words)
    return en > de


# STRICT = True  -> only jobs whose text explicitly asks for English AND does not require German
# STRICT = False -> English-language posting that does not require German (more results)
STRICT = True

EN_REQ = re.compile(
    r"(fluent|fluency|proficien\w*|excellent|good|strong|business[- ]level|professional|full)"
    r"\s+(written\s+and\s+spoken\s+|spoken\s+and\s+written\s+)?(in\s+)?english"
    r"|english\s+(language\s+)?(skills|proficiency|fluency|level|is required|is a must|required|is mandatory|speaking)"
    r"|working language is english|company language is english|corporate language is english"
    r"|english[- ]speaking|communicat\w+ in english|business english"
    r"|(spoken|written)( and (spoken|written))? english|english (c1|c2|b2)|(c1|c2|b2)[^.]{0,20}english",
    re.I)

DE_REQ = re.compile(
    r"(fluent|fluency|proficien\w*|excellent|good|strong|native|business[- ]level|very good)\s+(in\s+)?german"
    r"|german\s+(language\s+)?(skills|proficiency|fluency|is required|required|is a must|mandatory|native)"
    r"|deutsch(kenntnisse)?\s+(verhandlungssicher|fließend|fliessend|erforderlich|muttersprache|c1|c2|b2)"
    r"|verhandlungssicher\w*\s+deutsch|fließend\w*\s+deutsch|german[- ]speaking|german (c1|c2|b2)|(c1|c2|b2)[^.]{0,20}german",
    re.I)

OPTIONAL = re.compile(r"plus|advantage|nice|bonus|benefici|desirable|welcome|asset|helpful|preferred", re.I)


def requires_german(text: str) -> bool:
    for m in DE_REQ.finditer(text):
        after = text[m.end(): m.end() + 40]
        before = text[max(0, m.start() - 40): m.start()]
        if not (OPTIONAL.search(after) or OPTIONAL.search(before)):
            return True
    return False


def english_ok(text: str) -> bool:
    """Decide whether a job passes the English-language requirement."""
    if requires_german(text):
        return False
    if STRICT:
        return bool(EN_REQ.search(text))
    return looks_english(text)


def title_matches(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in TITLE_KEYWORDS)


def in_nrw(location: str) -> bool:
    loc = (location or "").lower()
    return any(p in loc for p in NRW_PLACES)


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
            if not english_ok(j["title"] + " " + re.sub(r"<[^>]+>", " ", j.get("description", ""))):
                continue
            loc = j.get("location", "")
            jobs.append({"title": j["title"], "company": j["company_name"],
                         "location": loc, "url": j["url"],
                         "source": "Arbeitnow", "nrw": in_nrw(loc)})
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
                if not english_ok(j["title"] + " " + j.get("description", "")):
                    continue
                loc = j.get("location", {}).get("display_name", "")
                jobs.append({"title": j["title"],
                             "company": j.get("company", {}).get("display_name", ""),
                             "location": loc,
                             "url": j["redirect_url"], "source": "Adzuna",
                             "nrw": in_nrw(loc)})
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
        return "<p>No new matching English-language jobs found today.</p>"

    def rows(items):
        return "".join(
            f'<li><a href="{html.escape(j["url"])}"><b>{html.escape(j["title"])}</b></a>'
            f' &ndash; {html.escape(j["company"])}, {html.escape(j["location"])}'
            f' <small>({j["source"]})</small></li>' for j in items)

    nrw = [j for j in jobs if j["nrw"]]
    other = [j for j in jobs if not j["nrw"]]
    body = f"<h3>North Rhine-Westphalia ({len(nrw)})</h3>"
    body += f"<ul>{rows(nrw)}</ul>" if nrw else "<p>No new NRW jobs today.</p>"
    body += f"<h3>Other cities in Germany ({len(other)})</h3>"
    body += f"<ul>{rows(other)}</ul>" if other else "<p>None.</p>"
    return body


def send(body, total, nrw_count):
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Germany IT Jobs (English): {total} new ({nrw_count} in NRW)"
    msg["From"], msg["To"] = user, TO_EMAIL
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.sendmail(user, [TO_EMAIL], msg.as_string())


if __name__ == "__main__":
    cutoff = time.time() - LOOKBACK_HOURS * 3600
    jobs = dedupe(fetch_arbeitnow(cutoff) + fetch_adzuna())
    nrw_count = sum(j["nrw"] for j in jobs)
    print(f"Found {len(jobs)} jobs ({nrw_count} in NRW)")
    send(build_email(jobs), len(jobs), nrw_count)
  
   
