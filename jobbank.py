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


def _find(cols, *words, avoid=()):
    for c in cols:
        lc = c.lower()
        if any(w in lc for w in words) and not any(a in lc for a in avoid):
            return c
    return None


def tidy(df):
    """Map Job Bank's columns to simple names the app uses."""
    cols = list(df.columns)
    pick = {
        "title": _find(cols, "job title", "title", "titre"),
        "employer": _find(cols, "employer", "employeur", "business", "entreprise", "company"),
        "city": _find(cols, "city", "ville", "municipal"),
        "province": _find(cols, "province", "territor"),
        "noc": _find(cols, "noc", "cnp"),
        "salary": _find(cols, "salary", "salaire", "wage"),
        "posting_id": _find(cols, "job posting id", "posting id", "job id", "numéro", "number", avoid=("noc", "naics", "vacanc", "phone")),
    }
    if not pick["title"]:
        raise ValueError("could not find a job title column. Columns found: " + ", ".join(map(str, cols[:40])))
    out = pd.DataFrame(index=df.index)
    for k, v in pick.items():
        out[k] = df[v] if v else ""
    out = out.replace({"NA": "", "N/A": ""})
    # one text column with everything, used later for matching
    out["all_text"] = df.astype(str).agg(" · ".join, axis=1)
    ids = out["posting_id"].astype(str).str.extract(r"(\d{5,})")[0]
    out["link"] = ("https://www.jobbank.gc.ca/jobsearch/jobposting/" + ids).where(ids.notna(), "")
    return out, pick
