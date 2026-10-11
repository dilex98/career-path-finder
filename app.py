"""Career Path Finder - capstone project (INDU 6993, Concordia).

Step 1: the box of jobs. Loads jobs from two kinds of sources:
  - Job Bank open data (Government of Canada, updated monthly)
  - company job feeds (Greenhouse, Lever, Ashby; updated every few hours)
Next steps (rank, explain, ask, update) are added on top of this page.
"""
import re

import pandas as pd
import streamlit as st

import feeds
import jobbank

st.set_page_config(page_title="Career Path Finder", page_icon="🧭", layout="wide")
st.title("Career Path Finder")
st.caption("Step 1 of the build: the box of jobs · Sources: Job Bank open data and company job sites")

COLUMNS = ["title", "employer", "occupation", "city", "province", "salary", "language", "education",
           "experience", "job_type", "posted", "source", "link", "description", "all_text"]

# Bump this number whenever the way jobs are read changes, so old cached tables are not reused.
DATA_VERSION = 4


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_files():
    return jobbank.list_files()


@st.cache_data(ttl=24 * 3600, show_spinner=False, max_entries=2)
def get_jobbank(url, version=DATA_VERSION):
    raw = jobbank.download(url)
    jobs, mapping = jobbank.tidy(raw)
    return jobs, mapping, list(raw.columns)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_company_jobs(version=DATA_VERSION):
    return feeds.load()


def complete(df):
    """Give every table the same columns so they can be stacked together."""
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNS].fillna("")


# ---- 1. choose the sources --------------------------------------------------
sources = st.multiselect("Job sources", ["Job Bank (government)", "Company job sites"],
                         default=["Job Bank (government)", "Company job sites"])
tables, notes = [], {}

if "Job Bank (government)" in sources:
    try:
        with st.spinner("Looking for the newest Job Bank file…"):
            files = get_files()
        if not files:
            raise RuntimeError("no English CSV files were listed")
        labels = [f["name"] for f in files]
        choice = st.selectbox("Job Bank month", labels, index=0,
                              help="The newest month is picked automatically. Job Bank publishes a new file every month.")
        with st.spinner("Downloading the Job Bank postings (the first time can take a minute)…"):
            jb, mapping, raw_cols = get_jobbank(files[labels.index(choice)]["url"])
        jb = jb.copy()
        jb["employer"] = ""
        jb["description"] = ""
        tables.append(complete(jb))
        notes["Job Bank"] = (raw_cols, mapping)
    except Exception as err:  # the government site can be slow or down
        st.warning(f"Could not download the Job Bank file automatically ({err}). "
                   f"You can download it from the [Job Bank data page]({jobbank.DATASET_PAGE}) and upload it here.")
        up = st.file_uploader("Upload a Job Bank CSV", type="csv")
        if up:
            raw = jobbank.read_csv_bytes(up.getvalue())
            jb, mapping = jobbank.tidy(raw)
            jb["employer"] = ""
            jb["description"] = ""
            tables.append(complete(jb))
            notes["Job Bank"] = (list(raw.columns), mapping)

company_status = None
if "Company job sites" in sources:
    with st.spinner("Collecting jobs from company job sites…"):
        cj, company_status = get_company_jobs()
    tables.append(complete(cj.copy()))

if not tables:
    st.info("Choose at least one job source above.")
    st.stop()

jobs = pd.concat(tables, ignore_index=True)

# ---- 2. filters ---------------------------------------------------------------
st.subheader("Find jobs")
c1, c2, c3 = st.columns([1, 1, 2])
provinces = sorted(p for p in jobs["province"].unique() if p)
default = [p for p in provinces if re.search(r"qu[eé]bec|^qc$", p, re.I)]
prov = c1.multiselect("Province", provinces, default=default)
city = c2.text_input("City contains", placeholder="e.g. Montréal")
words = c3.text_input("Keywords in the job title", placeholder="e.g. analyst, nurse, accountant, développeur")

view = jobs
if prov:
    view = view[view["province"].isin(prov)]
if city.strip():
    view = view[view["city"].str.contains(city.strip(), case=False, na=False)]
    st.caption("Many Job Bank postings have no city, so a city filter hides them.")
if words.strip():
    pattern = "|".join(re.escape(w.strip()) for w in words.split(",") if w.strip())
    view = view[view["title"].str.contains(pattern, case=False, na=False, regex=True)]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Jobs loaded", f"{len(jobs):,}")
m2.metric("Matching your filters", f"{len(view):,}")
m3.metric("From Job Bank", f"{(view['source'] != 'Company site').sum():,}")
m4.metric("From company sites", f"{(view['source'] == 'Company site').sum():,}")

show = view[["title", "employer", "occupation", "city", "province", "salary", "language", "education",
             "experience", "job_type", "posted", "source", "link"]].head(2000)
st.dataframe(
    show, width="stretch", hide_index=True,
    column_config={
        "title": "Job title", "employer": "Employer", "occupation": "Occupation (NOC)",
        "city": "City or region", "province": "Province", "salary": "Salary", "language": "Language",
        "education": "Education", "experience": "Experience", "job_type": "Type",
        "posted": "Posted", "source": "Source",
        "link": st.column_config.LinkColumn("Link", display_text="Open"),
    },
)
st.caption("Job Bank's open data has no employer names or job descriptions; company-site jobs have both. "
           "Job Bank links open a search for that title; company-site links open the real posting.")
if len(view) > 2000:
    st.caption("Showing the first 2,000 matches. Add a keyword to narrow the list.")

# ---- 3. for the team ---------------------------------------------------------
with st.expander("Where do the jobs come from? (for the team)"):
    if company_status is not None:
        st.write("**Company job sites** (only jobs located in Canada are kept). "
                 "To add a company, add one line to `COMPANIES` in `feeds.py`.")
        st.dataframe(company_status, hide_index=True, width="stretch")
    if "Job Bank" in notes:
        raw_cols, mapping = notes["Job Bank"]
        st.write("**Job Bank file** – columns found:", raw_cols)
        st.write("How the app reads them:", {k: v or "not found" for k, v in mapping.items()})
