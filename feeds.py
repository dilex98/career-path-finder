"""Company job feeds - jobs posted directly by employers.

Many companies publish their open jobs through hiring software (Greenhouse,
Lever, Ashby) that offers a free, public, official feed. Unlike the Job Bank
open-data file, these feeds include the employer name, the full job
description and a link to the real posting.

To add a company: find its careers page address, e.g.
  job-boards.greenhouse.io/poka   ->  ("greenhouse", "poka", "Poka")
  jobs.lever.co/eqbank            ->  ("lever", "eqbank", "EQ Bank")
  jobs.ashbyhq.com/cohere         ->  ("ashby", "cohere", "Cohere")
and add a line to COMPANIES below. A company whose feed does not answer is
simply skipped and listed as "not reachable" in the app.
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import requests

# (hiring system, board name in its web address, company name to show)
COMPANIES = [
    ("greenhouse", "poka", "Poka"),
    ("greenhouse", "maintainx", "MaintainX"),
    ("greenhouse", "lightspeedhq", "Lightspeed Commerce"),
    ("greenhouse", "coveo", "Coveo"),
    ("greenhouse", "mila", "Mila"),
    ("greenhouse", "hopper", "Hopper"),
    ("greenhouse", "dialogue", "Dialogue"),
    ("greenhouse", "nuvei", "Nuvei"),
    ("greenhouse", "ssense", "SSENSE"),
    ("greenhouse", "benevity", "Benevity"),
    ("greenhouse", "clio", "Clio"),
    ("greenhouse", "hootsuite", "Hootsuite"),
    ("lever", "keyloop", "Keyloop"),
    ("lever", "alimentiv-2", "Alimentiv"),
    ("lever", "immiland-canada-inc", "Immiland Canada"),
    ("lever", "getmaple", "Maple"),
    ("lever", "eqbank", "EQ Bank"),
    ("lever", "kong", "Kong"),
    ("lever", "hopper", "Hopper"),
    ("ashby", "cohere", "Cohere"),
    ("ashby", "wealthsimple", "Wealthsimple"),
    ("ashby", "1password", "1Password"),
]

CITY_PROVINCE = {
    "montreal": "Quebec", "montréal": "Quebec", "laval": "Quebec", "quebec": "Quebec", "québec": "Quebec",
    "sherbrooke": "Quebec", "gatineau": "Quebec", "longueuil": "Quebec", "boucherville": "Quebec",
    "saint-laurent": "Quebec", "dorval": "Quebec", "levis": "Quebec", "lévis": "Quebec",
    "toronto": "Ontario", "ottawa": "Ontario", "waterloo": "Ontario", "kitchener": "Ontario",
    "mississauga": "Ontario", "london, on": "Ontario", "markham": "Ontario", "hamilton": "Ontario",
    "vancouver": "British Columbia", "burnaby": "British Columbia", "victoria": "British Columbia",
    "calgary": "Alberta", "edmonton": "Alberta", "winnipeg": "Manitoba", "regina": "Saskatchewan",
    "saskatoon": "Saskatchewan", "halifax": "Nova Scotia", "fredericton": "New Brunswick",
    "moncton": "New Brunswick", "st. john's": "Newfoundland and Labrador",
}
PROVINCE_WORDS = {
    "quebec": "Quebec", "québec": "Quebec", ", qc": "Quebec", "ontario": "Ontario", ", on": "Ontario",
    "british columbia": "British Columbia", ", bc": "British Columbia", "alberta": "Alberta", ", ab": "Alberta",
    "manitoba": "Manitoba", "saskatchewan": "Saskatchewan", "nova scotia": "Nova Scotia",
    "new brunswick": "New Brunswick",
}
CANADA = re.compile(r"canada|"
                    + "|".join(re.escape(c) for c in CITY_PROVINCE)
                    + r"|\b(qc|on|bc|ab)\b", re.I)


def _plain(text):
    """Turn an HTML job description into plain text."""
    text = html.unescape(text or "")
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _place(location):
    """Find the city and province in a location like 'Montréal, QC, Canada'."""
    low = (location or "").lower()
    for city, prov in CITY_PROVINCE.items():
        if city in low:
            return city.title() if city.isascii() else location.split(",")[0].strip(), prov
    for word, prov in PROVINCE_WORDS.items():
        if word in low:
            return "", prov
    return "", ""


def _date(value):
    if not value:
        return ""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y/%m/%d")
        return str(value)[:10].replace("-", "/")
    except Exception:
        return ""


def _greenhouse(token, name):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    for j in requests.get(url, timeout=20).json().get("jobs", []):
        yield {"title": j.get("title", ""), "employer": name,
               "location": (j.get("location") or {}).get("name", ""),
               "description": _plain(j.get("content")), "link": j.get("absolute_url", ""),
               "posted": _date(j.get("updated_at"))}


def _lever(token, name):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    for j in requests.get(url, timeout=20).json():
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location", "")]
        lists = " ".join(f"{l.get('text', '')}: {_plain(l.get('content'))}" for l in j.get("lists", []))
        yield {"title": j.get("text", ""), "employer": name, "location": " / ".join(filter(None, locs)),
               "description": " ".join([j.get("descriptionPlain", ""), lists, j.get("additionalPlain", "")]),
               "link": j.get("hostedUrl", ""), "posted": _date(j.get("createdAt")),
               "job_type": cat.get("commitment", "")}


def _ashby(token, name):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    for j in requests.get(url, timeout=20).json().get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", []) or []]
        country = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or "")
        yield {"title": j.get("title", ""), "employer": name,
               "location": " / ".join(filter(None, locs)) + (f", {country}" if country else ""),
               "description": j.get("descriptionPlain", "") or _plain(j.get("descriptionHtml")),
               "link": j.get("jobUrl", ""), "posted": _date(j.get("publishedAt")),
               "job_type": j.get("employmentType", "")}


FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}


def _one(company):
    ats, token, name = company
    try:
        rows = [r for r in FETCHERS[ats](token, name) if CANADA.search(r["location"])]
        return rows, {"company": name, "system": ats, "board": token, "jobs in Canada": len(rows), "status": "ok"}
    except Exception as err:
        return [], {"company": name, "system": ats, "board": token, "jobs in Canada": 0,
                    "status": f"not reachable ({type(err).__name__})"}


def experience_years(text):
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|ans)\b", text or "", re.I)
    return f"{m.group(1)}+ years" if m else ""


def language(text):
    t = (text or "").lower()
    if re.search(r"bilingu|french and english|english and french|français et anglais|anglais et français", t):
        return "English and French"
    if re.search(r"\bfrench\b|français", t):
        return "French mentioned"
    return ""


def load(companies=None):
    """Fetch all company feeds at once; return (jobs table, status table)."""
    companies = companies or COMPANIES
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_one, companies))
    rows = [r for rs, _ in results for r in rs]
    status = pd.DataFrame([s for _, s in results])
    df = pd.DataFrame(rows, columns=["title", "employer", "location", "description", "link", "posted", "job_type"])
    df = df.fillna("")
    places = df["location"].map(_place)
    df["city"] = [c or loc.split(",")[0] for (c, _), loc in zip(places, df["location"])]
    df["province"] = [p for _, p in places]
    df["occupation"] = ""
    df["salary"] = ""
    df["education"] = ""
    df["experience"] = df["description"].map(experience_years)
    df["language"] = df["description"].map(language)
    df["source"] = "Company site"
    df["all_text"] = df["title"] + " · " + df["description"]
    return df.drop_duplicates(subset=["title", "employer", "location"]), status
