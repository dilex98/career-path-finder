# Career Path Finder

Capstone project, INDU 6993, Concordia University (Loïg Glo, Dilex Manirambona, Anmol Dutt, Clémence Delmont Magazzeni).

**Live app:** https://careerpathfinderrr.streamlit.app

**Goal:** help job seekers in Canada find the jobs they can realistically get, and plan the path to the role they want.

## Build steps
1. **The box of jobs** – Job Bank open data (monthly) + company job sites on Greenhouse, Lever and Ashby (every few hours) ← *current*
2. The reader – reads a PDF or Word CV
3. The judge – ranks jobs and explains fit and gaps
4. The question-asker – asks about missing skills and must-haves, then updates the list
5. The mail sorter – tracks applications from job emails
6. The map – career path to the goal role

## Files
- `app.py` – the website (Streamlit)
- `jobbank.py` – finds and downloads the newest Job Bank file
- `feeds.py` – reads company job feeds from 7 open hiring systems (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, BambooHR); add a company with one line in `COMPANIES`
- `finder.py` – company finder: checks a list of Canadian employers on every open system and keeps those with jobs in Canada
- `oasis.py` – official occupation profiles (OaSIS) attached to Job Bank jobs
- `eligibility.py` – reads who can apply (work permit) from job text and compares it with the applicant's status
- `requirements.txt` – Python packages the website needs

Data: [Job Bank open data](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072), Open Government Licence – Canada.
