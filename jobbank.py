"""Step 1 - The box of jobs.

Finds the newest Job Bank open-data file (Government of Canada, monthly),
downloads it, and turns it into a clean table of postings.
"""
import io
import re

import pandas as pd
import requests

DATASET_API = ("https://open.canada.ca/data/api/action/package_show"
               "?id=ea639e28-c0fc-48bf-b5dd-b8899bd43072")
DATASET_PAGE = "https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _month_key(text):
    """Turn 'job-bank-...-en-aug2026.csv' into (2026, 8) so files sort by month."""
    t = text.lower()
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_ ]?(20\d\d)", t)
    if m:
        return int(m.group(2)), MONTHS[m.group(1)]
    m = re.search(r"(20\d\d)[-_]?(\d\d)", t)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def list_files():
    """Return the English CSV files of the dataset, newest first."""
    data = requests.get(DATASET_API, timeout=30).json()["result"]
    files = []
    for r in data["resources"]:
        lang = r.get("language") or []
        url = r.get("url", "")
        if (r.get("format", "").upper() == "CSV" and ("en" in lang or "-en-" in url.lower())):
            files.append({"name": r.get("name", url), "url": url,
                          "key": _month_key(url + " " + r.get("name", ""))})
    files.sort(key=lambda f: f["key"], reverse=True)
    return files


def read_csv_bytes(raw):
    """Read a Job Bank CSV, whatever its encoding or separator."""
    if raw[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
        raise ValueError("the government site sent a web page instead of the data file")
    # Job Bank files are often UTF-16 (BOM \xff\xfe or lots of zero bytes)
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encodings = ("utf-16",)
    elif raw[:4000].count(b"\x00") > 500:
        encodings = ("utf-16-le",) if raw[1:2] == b"\x00" else ("utf-16-be",)
    else:
        encodings = ("utf-8-sig", "cp1252", "latin-1")
    text = None
    for enc in encodings:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("latin-1")
    text = text.lstrip("\ufeff")
    first = text.split("\n", 1)[0]
    sep = max([",", "\t", ";"], key=first.count)
    return pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)


def download(url):
    raw = requests.get(url, timeout=180).content
    return read_csv_bytes(raw)


def _norm(name):
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def _find(cols, *names):
    """Return the first column whose name contains one of `names`."""
    normed = {c: _norm(c) for c in cols}
    for n in names:
        for c, nc in normed.items():
            if nc == n:
                return c
    for n in names:
        for c, nc in normed.items():
            if n in nc:
                return c
    return None


# What the Job Bank file calls each piece of information (checked on the 2026 files).
# Note: the open-data file has NO employer name and NO job description,
# and the city is often blank ("NA"), especially for postings from partner sites.
FIELDS = {
    "title": ("job title",),
    "occupation": ("noc21 code name", "noc 2021 code name", "noc code name"),
    "noc": ("noc21 code", "noc 2021 code"),
    "province": ("province/territory", "province"),
    "city": ("city",),
    "region": ("economic region",),
    "salary": ("salary condition detail", "salary"),
    "salary_min": ("salary minimum",),
    "salary_max": ("salary maximum",),
    "salary_per": ("salary per",),
    "language": ("official language",),
    "education": ("education los", "education"),
    "experience": ("experience level", "experience"),
    "job_type": ("employment type",),
    "term": ("employment term",),
    "posted": ("first posting date", "posting date"),
    "external": ("external indicator",),
}

EMPTY = {"NA": "", "N/A": "", "*No data": "", "nan": "", "None": ""}


def tidy(df):
    """Map Job Bank's columns to simple names the app uses."""
    cols = list(df.columns)
    pick = {k: _find(cols, *names) for k, names in FIELDS.items()}
    if not pick["title"]:
        raise ValueError("could not find a job title column. Columns found: " + ", ".join(map(str, cols[:40])))
    out = pd.DataFrame(index=df.index)
    for k, v in pick.items():
        out[k] = df[v].astype(str).str.strip() if v else ""
    out = out.replace(EMPTY)
    out["city"] = out["city"].where(out["city"] != "", out["region"])
    out["source"] = out["external"].map({"1": "Partner site", "0": "Job Bank"}).fillna("")
    # one text column with everything, used later for matching
    out["all_text"] = df.astype(str).agg(" · ".join, axis=1)
    # the file has no posting ID, so link to a Job Bank search for the same title and province
    q = out["title"].str.replace(" ", "+", regex=False)
    p = out["province"].str.replace(" ", "+", regex=False)
    out["link"] = "https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=" + q + "&locationstring=" + p
    return clean(out), pick


# ---- making the fields comparable ------------------------------------------
# Hours per period used to turn hourly/weekly/monthly pay into a yearly figure
# (assumption: 40 h/week, 52 weeks; shown in the app as an estimate).
YEARLY = {"hour": 2080, "day": 260, "week": 52, "month": 12, "year": 1, "annual": 1}

EDUCATION_LEVELS = [  # (pattern, level number, label) - checked in this order
    (r"no degree|no formal|none required", 1, "No degree required"),
    (r"doctor|ph\.?d", 6, "Doctorate"),
    (r"master", 5, "Master's degree"),
    (r"bachelor|baccalaur|university", 4, "Bachelor's degree"),
    (r"college|cegep|cégep|diploma|certificate.*(college|trade)|apprentice|trade|vocational|professional training",
     3, "College, CEGEP, trade or apprenticeship"),
    (r"secondary|high school|secondaire", 2, "Secondary (high) school"),
]


def _money(x):
    try:
        return float(str(x).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def _yearly(row):
    per = str(row["salary_per"]).strip().lower()
    factor = next((v for k, v in YEARLY.items() if k in per), None)
    lo, hi = _money(row["salary_min"]), _money(row["salary_max"])
    if factor is None or lo is None:
        return pd.Series([None, None])
    hi = hi if hi is not None else lo
    return pd.Series([round(lo * factor), round(hi * factor)])


def _education(text):
    t = str(text).lower()
    if not t.strip():
        return pd.Series([None, ""])
    for pattern, level, label in EDUCATION_LEVELS:
        if re.search(pattern, t):
            return pd.Series([level, label])
    return pd.Series([None, str(text)])


def _experience(text):
    """'1 year to less than 2 years' -> 1.0 ; '7 months to less than 1 year' -> 0.6 ; 'No experience' -> 0."""
    t = str(text).lower()
    if not t.strip():
        return None
    if "no experience" in t or "will train" in t:
        return 0.0
    m = re.search(r"(\d+)\s*(year|month)", t)
    if not m:
        return None
    n = float(m.group(1))
    return round(n / 12, 1) if m.group(2) == "month" else n


def _language(text):
    t = str(text).lower()
    has_en, has_fr = "english" in t or "anglais" in t, "french" in t or "français" in t
    if "bilingual" in t or (has_en and has_fr and " and " in t):
        return "English and French"
    if has_en and has_fr:
        return "English or French"
    if has_fr:
        return "French"
    if has_en:
        return "English"
    return ""


def clean(out):
    out["noc"] = out["noc"].astype(str).str.extract(r"(\d{4,5})")[0].fillna("").str.zfill(5).replace("00000", "")
    out[["salary_year_min", "salary_year_max"]] = out.apply(_yearly, axis=1)
    out[["education_level", "education"]] = out["education"].apply(_education)
    out["experience_years"] = out["experience"].map(_experience)
    out["language"] = out["language"].map(_language)
    out["posted_date"] = pd.to_datetime(out["posted"], errors="coerce", format="mixed")
    return out
