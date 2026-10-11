"""Career Path Finder - capstone project (INDU 6993, Concordia).

Step 1: the box of jobs.
  - Job Bank open data (Government of Canada, monthly), cleaned so salary,
    education, experience, language and dates can be compared.
  - Each Job Bank job gets the official profile of its occupation (OaSIS):
    what the occupation is, its main duties, usual requirements and key skills.
  - Company job sites (Greenhouse, Lever, Ashby) are optional.
Next steps (read the CV, rank, explain, ask, update) build on this page.
"""
import re

import pandas as pd
import streamlit as st

import feeds
import jobbank
import oasis

st.set_page_config(page_title="Career Path Finder", page_icon="🧭", layout="wide")
st.title("Career Path Finder")
st.caption("Step 1 of the build: the box of jobs · Job Bank open data + official occupation profiles (OaSIS)")

COLUMNS = ["title", "employer", "occupation", "noc", "city", "province", "salary", "salary_year_min",
           "salary_year_max", "language", "education", "education_level", "experience", "experience_years",
           "job_type", "posted", "posted_date", "source", "link", "description", "all_text"]
NUMERIC = ["salary_year_min", "salary_year_max", "education_level", "experience_years"]

# Bump this number whenever the way jobs are read changes, so old cached tables are not reused.
DATA_VERSION = 5


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_files():
    return jobbank.list_files()


@st.cache_data(ttl=24 * 3600, show_spinner=False, max_entries=2)
def get_jobbank(url, version=DATA_VERSION):
    raw = jobbank.download(url)
    jobs, mapping = jobbank.tidy(raw)
    return jobs, mapping, list(raw.columns)


@st.cache_data(ttl=30 * 24 * 3600, show_spinner=False)
def get_profiles(version=DATA_VERSION):
    return oasis.load()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_company_jobs(version=DATA_VERSION):
    return feeds.load()


def complete(df):
    """Give every table the same columns so they can be stacked together."""
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None if col in NUMERIC + ["posted_date"] else ""
    df = df[COLUMNS].copy()
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce")
    text_cols = [c for c in COLUMNS if c not in NUMERIC + ["posted_date"]]
    df[text_cols] = df[text_cols].fillna("")
    return df


def pct(series):
    return f"{100 * series.mean():.0f}%" if len(series) else "–"


# ---- 1. load the data ---------------------------------------------------------
sources = st.multiselect("Job sources", ["Job Bank (government)", "Company job sites"],
                         default=["Job Bank (government)"],
                         help="Company job sites add employer names and full descriptions, but far fewer jobs.")
tables, notes = [], {}

with st.spinner("Loading official occupation profiles (OaSIS)…"):
    profiles, oasis_status = get_profiles()

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
        tables.append(complete(jb.copy()))
        notes["Job Bank"] = (raw_cols, mapping)
    except Exception as err:  # the government site can be slow or down
        st.warning(f"Could not download the Job Bank file automatically ({err}). "
                   f"You can download it from the [Job Bank data page]({jobbank.DATASET_PAGE}) and upload it here.")
        up = st.file_uploader("Upload a Job Bank CSV", type="csv")
        if up:
            raw = jobbank.read_csv_bytes(up.getvalue())
            jb, mapping = jobbank.tidy(raw)
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
jobs["has_profile"] = jobs["noc"].isin(profiles.keys())
# The text the CV will be compared with later: the posting itself plus its occupation profile.
jobs["all_text"] = jobs["all_text"] + " · " + jobs["noc"].map(lambda n: oasis.profile_text(profiles.get(n)))

# ---- 2. filters ---------------------------------------------------------------
st.subheader("Find jobs")
r1 = st.columns([1, 2, 1])
provinces = sorted(p for p in jobs["province"].unique() if p)
prov = r1[0].multiselect("Province", provinces,
                         default=[p for p in provinces if re.search(r"qu[eé]bec|^qc$", p, re.I)])
words = r1[1].text_input("Keywords in the job title or occupation",
                         placeholder="e.g. analyst, nurse, accountant, développeur")
posted_within = r1[2].selectbox("Posted within", ["Any time", "7 days", "14 days", "30 days", "60 days"])

r2 = st.columns(4)
edu_labels = ["Any", "No degree required", "Secondary (high) school", "College, CEGEP, trade or apprenticeship",
              "Bachelor's degree", "Master's degree", "Doctorate"]
my_edu = r2[0].selectbox("My highest education", edu_labels,
                         help="Hides jobs that ask for more education than this. Jobs that don't say are kept.")
my_exp = r2[1].selectbox("My years of experience", ["Any", 0, 1, 2, 3, 5, 10],
                         help="Hides jobs that ask for more experience than this. Jobs that don't say are kept.")
min_pay = r2[2].number_input("Minimum yearly pay ($)", min_value=0, max_value=300000, value=0, step=5000,
                             help="Estimated: hourly pay × 2,080 hours. Jobs without a salary are kept.")
langs = r2[3].multiselect("Language of work", ["English", "French", "English and French", "English or French"])

view = jobs
if prov:
    view = view[view["province"].isin(prov)]
if words.strip():
    pattern = "|".join(re.escape(w.strip()) for w in words.split(",") if w.strip())
    view = view[view["title"].str.contains(pattern, case=False, na=False, regex=True)
                | view["occupation"].str.contains(pattern, case=False, na=False, regex=True)]
if posted_within != "Any time":
    newest = jobs["posted_date"].max()
    days = int(posted_within.split()[0])
    view = view[view["posted_date"].isna() | (view["posted_date"] >= newest - pd.Timedelta(days=days))]
if my_edu != "Any":
    lvl = edu_labels.index(my_edu)
    view = view[view["education_level"].isna() | (view["education_level"] <= lvl)]
if my_exp != "Any":
    view = view[view["experience_years"].isna() | (view["experience_years"] <= my_exp)]
if min_pay:
    view = view[view["salary_year_max"].isna() | (view["salary_year_max"] >= min_pay)]
if langs:
    view = view[view["language"].isin(langs)]

view = view.sort_values("posted_date", ascending=False, na_position="last")

m = st.columns(4)
m[0].metric("Jobs loaded", f"{len(jobs):,}")
m[1].metric("Matching your filters", f"{len(view):,}")
m[2].metric("Occupations", f"{view['noc'].replace('', pd.NA).nunique():,}")
m[3].metric("With an occupation profile", pct(view["has_profile"]))

# ---- 3. the table, with a click to see details ------------------------------------
view = view.assign(occupation_link=view["noc"].map(oasis.occupation_url))
table = view[["title", "employer", "occupation", "occupation_link", "city", "province", "salary", "salary_year_min",
              "salary_year_max", "language", "education", "experience", "job_type", "posted", "source",
              "link"]].head(2000)
st.info("👉 Tick the small box at the left of a row to open that job's details and its occupation profile below the table. "
        "The **View** link opens the official occupation page on the Government of Canada website.")
event = st.dataframe(
    table, width="stretch", hide_index=True, on_select="rerun", selection_mode="single-row", key="jobs_table",
    column_config={
        "title": "Job title", "employer": "Employer", "occupation": "Occupation (NOC)",
        "city": "City or region", "province": "Province", "salary": "Salary (as posted)",
        "salary_year_min": st.column_config.NumberColumn("Yearly from (est.)", format="$%d"),
        "salary_year_max": st.column_config.NumberColumn("Yearly to (est.)", format="$%d"),
        "language": "Language", "education": "Education", "experience": "Experience",
        "job_type": "Type", "posted": "Posted", "source": "Source",
        "link": st.column_config.LinkColumn("Job posting", display_text="Open"),
        "occupation_link": st.column_config.LinkColumn("Occupation details", display_text="View",
                                                       help="Official Government of Canada page for this occupation"),
    },
)
if len(view) > 2000:
    st.caption("Showing the 2,000 newest matches. Add a keyword or a filter to narrow the list.")

rows = event.selection.rows if event and event.selection else []
if rows:
    job = table.iloc[rows[0]]
    full = view.loc[table.index[rows[0]]]
    st.subheader(job["title"].capitalize())
    left, right = st.columns([1, 2])
    with left:
        st.markdown("**What the posting says**")
        facts = {
            "Employer": job["employer"] or "Not given in Job Bank's open data",
            "Occupation": f"{job['occupation']} (NOC {full['noc']})" if full["noc"] else job["occupation"],
            "Where": ", ".join(x for x in [job["city"], job["province"]] if x) or "Not given",
            "Salary": job["salary"] or "Not given",
            "Education": job["education"] or "Not given",
            "Experience": job["experience"] or "Not given",
            "Language": job["language"] or "Not given",
            "Type": job["job_type"] or "Not given",
            "Posted": job["posted"] or "Not given",
        }
        for k, v in facts.items():
            st.markdown(f"- **{k}:** {v}")
        if job["link"]:
            st.link_button("Open on " + ("the company site" if job["source"] == "Company site" else "Job Bank"),
                           job["link"])
        if full["noc"]:
            st.link_button("Occupation details (Government of Canada)", oasis.occupation_url(full["noc"]))
    with right:
        if full["description"]:
            st.markdown("**Job description** 🟢 *from the employer's posting*")
            st.write(full["description"][:3000])
        p = profiles.get(full["noc"])
        if p:
            st.markdown("**Typical duties and skills for this occupation** 🟡 "
                        "*official profile from the Government of Canada (OaSIS), not this employer's posting*")
            if p["lead"]:
                st.write(p["lead"])
            if p["duties"]:
                st.markdown("*Main duties*\n" + "\n".join(f"- {d}" for d in p["duties"]))
            if p["skills"]:
                st.markdown("*Most important skills:* " + ", ".join(p["skills"]))
            if p["requirements"]:
                st.markdown("*Usual requirements*\n" + "\n".join(f"- {r}" for r in p["requirements"]))
        elif not full["description"]:
            st.info("No description or occupation profile is available for this job.")

# ---- 4. data quality and sources (for the team and the report) -------------------
with st.expander("Data quality: how complete is the information? (for the team and the report)"):
    jbv = jobs[jobs["source"] != "Company site"]
    if len(jbv):
        quality = pd.DataFrame({
            "Information": ["Occupation profile (OaSIS)", "Salary", "Education", "Experience", "Language",
                            "City or region", "Employer name", "Job description"],
            "Share of Job Bank jobs that have it": [
                pct(jbv["has_profile"]), pct(jbv["salary_year_min"].notna()), pct(jbv["education_level"].notna()),
                pct(jbv["experience_years"].notna()), pct(jbv["language"] != ""), pct(jbv["city"] != ""),
                pct(jbv["employer"] != ""), pct(jbv["description"] != "")],
        })
        st.write(f"Job Bank file: **{len(jbv):,} postings**.")
        st.dataframe(quality, hide_index=True, width="stretch")
        st.caption("Yearly pay is an estimate: hourly × 2,080 hours (40 h × 52 weeks), weekly × 52, monthly × 12.")
    st.write("**Occupation profiles (OaSIS 2025):**", f"{len(profiles):,} occupations loaded.")
    st.dataframe(oasis_status, hide_index=True, width="stretch")
    st.markdown(f"Sources: [Job Bank open data]({jobbank.DATASET_PAGE}) · [OaSIS]({oasis.DATASET_PAGE}) "
                "· Open Government Licence – Canada.")

with st.expander("Where do the jobs come from? (for the team)"):
    if company_status is not None:
        st.write("**Company job sites** (only jobs located in Canada are kept). "
                 "To add a company, add one line to `COMPANIES` in `feeds.py`.")
        st.dataframe(company_status, hide_index=True, width="stretch")
    if "Job Bank" in notes:
        raw_cols, mapping = notes["Job Bank"]
        st.write("**Job Bank file** – columns found:", raw_cols)
        st.write("How the app reads them:", {k: v or "not found" for k, v in mapping.items()})
