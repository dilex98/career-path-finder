"""Occupation profiles from OaSIS (Government of Canada).

OaSIS (Occupational and Skills Information System, ESDC) describes every
National Occupational Classification (NOC 2021) occupation: what it is
(lead statement), its main duties, its usual employment requirements and
how important each skill is (rated 0 to 5).

Job Bank's open-data file gives each posting an occupation code but no job
description, so we attach the matching OaSIS profile to every Job Bank job.
This is a description of the *occupation*, not of the employer's posting,
and the app always labels it that way.

Source: https://open.canada.ca/data/en/dataset/10ce43bd-fb58-4969-806b-4bffebc87bec
Licence: Open Government Licence - Canada.
"""
import re

import pandas as pd
import requests

import jobbank

DATASET_PAGE = "https://open.canada.ca/data/en/dataset/10ce43bd-fb58-4969-806b-4bffebc87bec"
_BASE = "https://open.canada.ca/data/dataset/10ce43bd-fb58-4969-806b-4bffebc87bec/resource/"
FILES = {
    "lead": _BASE + "d2a00c9b-2b7d-458f-a41f-10011d8164c7/download/lead-statement_oasis_2025_v1.0.csv",
    "duties": _BASE + "92e4107e-a804-4126-85ec-1fca23b82d81/download/main-duties_oasis-2025_v1.1.csv",
    "requirements": _BASE + "33b4ccb4-e725-4618-ab0b-f64c979ab9cc/download/employment-requirements_oasis_2025_v1.0.csv",
    "skills": _BASE + "bd9cf3f2-4cd5-47b1-ba74-ab68cd0a941b/download/skills_oasis_2025_v1.1.csv",
    "titles": _BASE + "3484364c-75a4-4e22-ae9a-d12ea72569d4/download/example-titles_oasis_2025_v1.0.csv",
}


def _get(url):
    return jobbank.read_csv_bytes(requests.get(url, timeout=120).content)


def _noc5(code):
    """'13201.00' -> '13201' (OaSIS profiles are sub-codes of a NOC occupation)."""
    m = re.match(r"\s*(\d{4,5})", str(code))
    return m.group(1).zfill(5) if m else ""


def _code_and_text(df):
    """Find the code column and the (first) text column of a long-format OaSIS table."""
    cols = [c for c in df.columns if c.strip().lower() not in ("_id", "")]
    code = next((c for c in cols if "code" in c.lower()), cols[0])
    text = next((c for c in cols if c != code and "label" not in c.lower() and "title" not in c.lower()), None)
    if text is None:
        text = next(c for c in cols if c != code)
    return code, text


def _long(df):
    """Group a long-format table (one row per item) into {noc5: [items]}."""
    code, text = _code_and_text(df)
    out = {}
    for c, t in zip(df[code], df[text]):
        k, t = _noc5(c), str(t).strip()
        if k and t and t.lower() != "nan" and t not in out.setdefault(k, []):
            out[k].append(t)
    return out


def _top_skills(df, n=8, minimum=3):
    """Skills table is wide: one column per skill, rated 0-5. Keep the highest per occupation."""
    code = next(c for c in df.columns if "code" in c.lower())
    skip = {code.lower(), "_id"}
    skill_cols = [c for c in df.columns if c.lower() not in skip and "label" not in c.lower()]
    out = {}
    for _, row in df.iterrows():
        k = _noc5(row[code])
        if not k:
            continue
        best = out.setdefault(k, {})
        for s in skill_cols:
            try:
                v = float(row[s])
            except (TypeError, ValueError):
                continue
            best[s] = max(best.get(s, 0), v)
    return {k: [s for s, v in sorted(d.items(), key=lambda x: -x[1]) if v >= minimum][:n] for k, d in out.items()}


def load():
    """Download OaSIS and return {noc5: profile dict} plus a status table."""
    tables, status = {}, []
    for name, url in FILES.items():
        try:
            tables[name] = _get(url)
            status.append({"table": name, "rows": len(tables[name]), "status": "ok"})
        except Exception as err:
            status.append({"table": name, "rows": 0, "status": f"not reachable ({type(err).__name__})"})
    lead = _long(tables["lead"]) if "lead" in tables else {}
    duties = _long(tables["duties"]) if "duties" in tables else {}
    reqs = _long(tables["requirements"]) if "requirements" in tables else {}
    titles = _long(tables["titles"]) if "titles" in tables else {}
    skills = _top_skills(tables["skills"]) if "skills" in tables else {}
    profiles = {}
    for k in set(lead) | set(duties) | set(reqs) | set(skills):
        profiles[k] = {
            "lead": " ".join(lead.get(k, [])[:2]),
            "duties": duties.get(k, [])[:12],
            "requirements": reqs.get(k, [])[:8],
            "skills": skills.get(k, []),
            "example_titles": titles.get(k, [])[:10],
        }
    return profiles, pd.DataFrame(status)


def profile_text(p):
    """One block of text per occupation, used later to compare with a CV."""
    if not p:
        return ""
    return " ".join([p["lead"], " ".join(p["duties"]), " ".join(p["requirements"]),
                     " ".join(p["skills"]), " ".join(p["example_titles"])])


def occupation_url(noc):
    """Official Government of Canada page for an occupation (NOC 2021)."""
    return (f"https://noc.esdc.gc.ca/Structure/NOCProfile?GocTemplateCulture=en-CA&code={noc}&version=2021.0"
            if noc else "")
