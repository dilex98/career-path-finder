"""Company job feeds - jobs posted directly by employers.

Many companies publish their open jobs through hiring software (an "applicant
tracking system") that offers a free, public, official feed. Unlike the Job
Bank open-data file, these feeds include the employer name, the full job
description and a link to the real posting, and a job is only in the feed
while it is open.

Open systems we read (each company has its own "board name" in the address):
  Greenhouse       job-boards.greenhouse.io/poka          -> ("greenhouse", "poka", "Poka")
  Lever            jobs.lever.co/eqbank                   -> ("lever", "eqbank", "EQ Bank")
  Ashby            jobs.ashbyhq.com/cohere                -> ("ashby", "cohere", "Cohere")
  SmartRecruiters  jobs.smartrecruiters.com/Ubisoft2      -> ("smartrecruiters", "Ubisoft2", "Ubisoft")
  Workable         apply.workable.com/acme                -> ("workable", "acme", "Acme")
  Recruitee        acme.recruitee.com                     -> ("recruitee", "acme", "Acme")
  BambooHR         acme.bamboohr.com/careers              -> ("bamboohr", "acme", "Acme")
Add a line to COMPANIES below, or use the "Add a company" box in the app.
A company whose feed does not answer is skipped and listed as "not reachable".
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import requests

HEADERS = {"User-Agent": "CareerPathFinder/1.0 (Concordia University capstone; open job feeds)",
           "Accept": "application/json"}
MAX_DETAILS = 80  # systems that need one call per job for the description: read at most this many per company


def _get(url, **kw):
    r = requests.get(url, headers=HEADERS, timeout=20, **kw)
    r.raise_for_status()
    return r.json()


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
    # ---- added from real careers-page links found on the web (October 2026) ----
    # Greenhouse
    ("greenhouse", "lightspeedhqfr", "Lightspeed (French board)"),
    ("greenhouse", "navigatr", "Navigatr"),
    ("greenhouse", "boostedai", "Boosted.ai"),
    ("greenhouse", "7shifts", "7shifts"),
    ("greenhouse", "versaterm", "Versaterm"),
    ("greenhouse", "behavox", "Behavox"),
    ("greenhouse", "vmlcanadaen", "VML Canada"),
    ("greenhouse", "appdirect", "AppDirect"),
    ("greenhouse", "quadbridge", "Quadbridge"),
    ("greenhouse", "doordashcanada", "DoorDash Canada"),
    ("greenhouse", "capintel", "CapIntel"),
    ("greenhouse", "stackadapt", "StackAdapt"),
    ("greenhouse", "englishcanada", "LAPORTE"),
    ("greenhouse", "saltxc", "SALT XC"),
    ("greenhouse", "wppmedia", "WPP Media"),
    # Lever
    ("lever", "potloc", "Potloc"),
    ("lever", "cirquedusoleil", "Cirque du Soleil"),
    ("lever", "mirego", "Mirego"),
    ("lever", "mistplay", "Mistplay"),
    ("lever", "bounteous", "Bounteous"),
    ("lever", "larian", "Larian Studios"),
    ("lever", "maquettevirtuelle", "Maquette Virtuelle"),
    ("lever", "tsmg", "TSMG"),
    ("lever", "aipconnect", "AIP Connect"),
    ("lever", "knix", "Knix"),
    ("lever", "ecosystem", "Ecosystem"),
    ("lever", "riocan", "RioCan"),
    ("lever", "swapcard", "Swapcard"),
    # Ashby
    ("ashby", "neofinancial", "Neo Financial"),
    ("ashby", "owner", "Owner.com"),
    ("ashby", "beaconsoftware", "Beacon Software"),
    ("ashby", "venn", "Venn"),
    ("ashby", "ramp", "Ramp"),
    # SmartRecruiters
    ("smartrecruiters", "TransatAT1", "Transat"),
    ("smartrecruiters", "torstar", "Torstar"),
    ("smartrecruiters", "GroupMCanada", "GroupM Canada"),
    ("smartrecruiters", "SpectrumHealthCare", "Spectrum Health Care"),
    ("smartrecruiters", "VentureMedia", "Venture Media"),
    ("smartrecruiters", "CatalystCanada", "Catalyst Canada"),
    ("smartrecruiters", "ampleinsightinc", "Ample Insight"),
    ("smartrecruiters", "paidiem", "PAIDIEM"),
    ("smartrecruiters", "OntarioTransitGroup", "Ontario Transit Group"),
    ("smartrecruiters", "Spruceinfotech2", "Spruce InfoTech"),
    ("smartrecruiters", "dexterra", "Dexterra"),
    ("smartrecruiters", "otipgroupofcompaniesogc", "OTIP Group of Companies"),
    ("smartrecruiters", "TheFamilyCentreOfNorthernAlberta", "The Family Centre of Northern Alberta"),
    ("smartrecruiters", "GoodwillIndustriesOntarioGreatLakes", "Goodwill Industries Ontario Great Lakes"),
    ("smartrecruiters", "EMCOCorporation", "EMCO Corporation"),
    # Workable
    ("workable", "export-development-canada", "Export Development Canada"),
    ("workable", "joey-restaurants-1", "JOEY Restaurants"),
    ("workable", "acuity-insights", "Acuity Insights"),
    ("workable", "bardel-entertainment", "Bardel Entertainment"),
    ("workable", "aviso", "Aviso Wealth"),
    ("workable", "entuitive", "Entuitive"),
    ("workable", "mscanada", "MS Canada"),
    ("workable", "veritree", "veritree"),
    ("workable", "sideinc", "Side"),
    ("workable", "tehora", "TEHORA"),
    # Recruitee
    ("recruitee", "huaweicanada", "Huawei Canada"),
    ("recruitee", "petalmd", "Petal"),
    ("recruitee", "ottawasafetycouncil", "Ottawa Safety Council"),
    ("recruitee", "ajwalter", "AJW Technique"),
    ("recruitee", "framestore", "Framestore"),
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


def _greenhouse(token, name, details=True):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content={'true' if details else 'false'}"
    for j in _get(url).get("jobs", []):
        yield {"title": j.get("title", ""), "employer": name,
               "location": (j.get("location") or {}).get("name", ""),
               "description": _plain(j.get("content")), "link": j.get("absolute_url", ""),
               "posted": _date(j.get("updated_at"))}


def _lever(token, name, details=True):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    for j in _get(url):
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location", "")]
        lists = " ".join(f"{l.get('text', '')}: {_plain(l.get('content'))}" for l in j.get("lists", []))
        yield {"title": j.get("text", ""), "employer": name, "location": " / ".join(filter(None, locs)),
               "description": " ".join([j.get("descriptionPlain", ""), lists, j.get("additionalPlain", "")]),
               "link": j.get("hostedUrl", ""), "posted": _date(j.get("createdAt")),
               "job_type": cat.get("commitment", "")}


def _ashby(token, name, details=True):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    for j in _get(url).get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", []) or []]
        country = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or "")
        yield {"title": j.get("title", ""), "employer": name,
               "location": " / ".join(filter(None, locs)) + (f", {country}" if country else ""),
               "description": j.get("descriptionPlain", "") or _plain(j.get("descriptionHtml")),
               "link": j.get("jobUrl", ""), "posted": _date(j.get("publishedAt")),
               "job_type": j.get("employmentType", "")}


def _smartrecruiters(token, name, details=True):
    base = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    jobs, offset = [], 0
    while True:
        page = _get(base, params={"country": "ca", "limit": 100, "offset": offset})
        jobs += page.get("content", [])
        offset += 100
        if offset >= page.get("totalFound", 0) or offset >= 1000:
            break

    def one(j):
        loc = j.get("location") or {}
        desc = ""
        if details:
            try:
                d = _get(f"{base}/{j['id']}")
                sec = (d.get("jobAd") or {}).get("sections") or {}
                desc = " ".join(_plain((sec.get(k) or {}).get("text")) for k in
                                ("jobDescription", "qualifications", "additionalInformation", "companyDescription"))
            except Exception:
                pass
        return {"title": j.get("name", ""), "employer": (j.get("company") or {}).get("name") or name,
                "location": loc.get("fullLocation") or ", ".join(filter(None, [loc.get("city"), loc.get("region")])),
                "country": loc.get("country", ""), "description": desc,
                "link": f"https://jobs.smartrecruiters.com/{token}/{j.get('id', '')}",
                "posted": _date(j.get("releasedDate")),
                "job_type": (j.get("typeOfEmployment") or {}).get("label", "")}
    with ThreadPoolExecutor(max_workers=6) as pool:
        yield from pool.map(one, jobs[:MAX_DETAILS] if details else jobs)


def _workable(token, name, details=True):
    data = _get(f"https://apply.workable.com/api/v1/widget/accounts/{token}", params={"details": "true"})
    for j in data.get("jobs", []):
        locs = j.get("locations") or [{"city": j.get("city"), "region": j.get("state"), "country": j.get("country")}]
        first = locs[0] if locs else {}
        yield {"title": j.get("title", ""), "employer": data.get("name") or name,
               "location": " / ".join(", ".join(filter(None, [l.get("city"), l.get("region") or l.get("state")]))
                                      for l in locs),
               "country": first.get("country") or first.get("countryCode") or j.get("country", ""),
               "description": _plain(j.get("description")),
               "link": j.get("url") or j.get("shortlink") or f"https://apply.workable.com/{token}/j/{j.get('shortcode', '')}",
               "posted": _date(j.get("published_on") or j.get("created_at")),
               "job_type": j.get("employment_type", "")}


def _recruitee(token, name, details=True):
    data = _get(f"https://{token}.recruitee.com/api/offers/")
    for j in data.get("offers", []):
        yield {"title": j.get("title", ""), "employer": j.get("company_name") or name,
               "location": j.get("location") or ", ".join(filter(None, [j.get("city"), j.get("state_name")])),
               "country": j.get("country_code") or j.get("country", ""),
               "description": _plain((j.get("description") or "") + " " + (j.get("requirements") or "")),
               "link": j.get("careers_url") or j.get("url", ""), "posted": _date(j.get("published_at")),
               "job_type": j.get("employment_type_code", "")}


def _bamboohr(token, name, details=True):
    base = f"https://{token}.bamboohr.com/careers"
    data = _get(f"{base}/list")
    jobs = data.get("result", []) if isinstance(data, dict) else data

    def one(j):
        loc = j.get("atsLocation") or j.get("location") or {}
        desc = ""
        if details:
            try:
                d = _get(f"{base}/{j['id']}/detail")
                desc = _plain(((d.get("result") or {}).get("jobOpening") or {}).get("description"))
            except Exception:
                pass
        return {"title": j.get("jobOpeningName", ""), "employer": name,
                "location": ", ".join(filter(None, [loc.get("city"), loc.get("state") or loc.get("province")])),
                "country": loc.get("country", ""), "description": desc,
                "link": f"{base}/{j.get('id', '')}", "posted": "",
                "job_type": j.get("employmentStatusLabel", "")}
    with ThreadPoolExecutor(max_workers=6) as pool:
        yield from pool.map(one, jobs[:MAX_DETAILS] if details else jobs)


FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby, "smartrecruiters": _smartrecruiters,
            "workable": _workable, "recruitee": _recruitee, "bamboohr": _bamboohr}


def in_canada(row):
    """Use the country when the feed gives one, otherwise look for Canadian places in the location."""
    country = str(row.get("country") or "").strip().lower()
    if country:
        return country in ("ca", "can", "canada")
    return bool(CANADA.search(row.get("location") or ""))


def _one(company, details=True):
    ats, token, name = company
    try:
        rows = [r for r in FETCHERS[ats](token, name, details) if in_canada(r)]
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
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(_one, companies))
    rows = [r for rs, _ in results for r in rs]
    status = pd.DataFrame([s for _, s in results]).sort_values("jobs in Canada", ascending=False)
    df = pd.DataFrame(rows, columns=["title", "employer", "location", "description", "link", "posted", "job_type"])
    df["location"] = df["location"].fillna("").astype(str)
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


URL_PATTERNS = [
    ("greenhouse", r"greenhouse\.io/(?:embed/job_board\?for=)?([\w-]+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/([\w-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([\w.-]+)"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)"),
    ("workable", r"apply\.workable\.com/([\w-]+)"),
    ("recruitee", r"([\w-]+)\.recruitee\.com"),
    ("bamboohr", r"([\w-]+)\.bamboohr\.com"),
]


def from_url(url):
    """Recognise the hiring system and board name in a careers-page address."""
    for ats, pattern in URL_PATTERNS:
        m = re.search(pattern, url or "", re.I)
        if m and m.group(1).lower() not in ("www", "api", "jobs", "boards", "job-boards", "app"):
            token = m.group(1)
            return ats, token, token.replace("-", " ").title()
    return None
