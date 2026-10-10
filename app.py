"""Career Path Finder - capstone project (INDU 6993, Concordia).

Step 1: the box of jobs. Loads the newest Job Bank file and lets you explore it.
Next steps (rank, explain, ask, update) are added on top of this page.
"""
import pandas as pd
import streamlit as st

import jobbank

st.set_page_config(page_title="Career Path Finder", page_icon="🧭", layout="wide")
st.title("Career Path Finder")
st.caption("Step 1 of the build: the box of jobs · Source: Job Bank open data, Government of Canada")


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_files():
    return jobbank.list_files()


@st.cache_data(ttl=24 * 3600, show_spinner=False, max_entries=2)
def get_jobs(url):
    raw = jobbank.download(url)
    jobs, mapping = jobbank.tidy(raw)
    return jobs, mapping, list(raw.columns)


# ---- 1. pick the month ------------------------------------------------------
jobs = None
try:
    with st.spinner("Looking for the newest Job Bank file…"):
        files = get_files()
    if not files:
        raise RuntimeError("no English CSV files were listed")
    labels = [f["name"] for f in files]
    choice = st.selectbox("Month", labels, index=0,
                          help="The newest month is picked automatically. Job Bank publishes a new file every month.")
    url = files[labels.index(choice)]["url"]
    with st.spinner("Downloading the postings (the first time can take a minute)…"):
        jobs, mapping, raw_cols = get_jobs(url)
except Exception as err:  # the government site can be slow or down
    st.warning(f"Could not download the Job Bank file automatically ({err}). "
               f"You can download it from the [Job Bank data page]({jobbank.DATASET_PAGE}) and upload it here.")
    up = st.file_uploader("Upload a Job Bank CSV", type="csv")
    if up:
        raw = jobbank.read_csv_bytes(up.getvalue())
        jobs, mapping = jobbank.tidy(raw)
        raw_cols = list(raw.columns)

if jobs is None:
    st.stop()

# ---- 2. filters ---------------------------------------------------------------
st.subheader("Find jobs")
c1, c2, c3 = st.columns([1, 1, 2])
provinces = sorted(p for p in jobs["province"].unique() if p)
default = [p for p in provinces if p.lower().startswith(("que", "qc"))]
prov = c1.multiselect("Province", provinces, default=default)
city = c2.text_input("City contains", placeholder="e.g. Montréal")
words = c3.text_input("Keywords in the job title", placeholder="e.g. analyst, nurse, accountant, développeur")

view = jobs
if prov:
    view = view[view["province"].isin(prov)]
if city.strip():
    view = view[view["city"].str.contains(city.strip(), case=False, na=False)]
if words.strip():
    pattern = "|".join(w.strip() for w in words.split(",") if w.strip())
    view = view[view["title"].str.contains(pattern, case=False, na=False, regex=True)]

m1, m2, m3 = st.columns(3)
m1.metric("Postings in the file", f"{len(jobs):,}")
m2.metric("Matching your filters", f"{len(view):,}")
m3.metric("Different employers", f"{view['employer'].nunique():,}")

show = view[["title", "employer", "city", "province", "salary", "noc", "link"]].head(2000)
st.dataframe(
    show, use_container_width=True, hide_index=True,
    column_config={
        "title": "Job title", "employer": "Employer", "city": "City", "province": "Province",
        "salary": "Salary", "noc": "Occupation code (NOC)",
        "link": st.column_config.LinkColumn("Posting", display_text="Open on Job Bank"),
    },
)
if len(view) > 2000:
    st.caption("Showing the first 2,000 matches. Add a keyword or a city to narrow the list.")

with st.expander("What is in the Job Bank file? (for the team)"):
    st.write("Columns found in the file:", raw_cols)
    st.write("How the app reads them:", {k: v or "not found" for k, v in mapping.items()})
