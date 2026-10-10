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
    return out, pick
