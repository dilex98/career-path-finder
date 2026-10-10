# Career Path Finder

Capstone project, INDU 6993, Concordia University (Loïg Glo, Dilex Manirambona, Anmol Dutt, Clémence Delmont Magazzeni).

**Goal:** help job seekers in Canada find the jobs they can realistically get, and plan the path to the role they want.

## Build steps
1. **The box of jobs** – loads the newest Job Bank open-data file (all fields) ← *current*
2. The reader – reads a PDF or Word CV
3. The judge – ranks jobs and explains fit and gaps
4. The question-asker – asks about missing skills and must-haves, then updates the list
5. The mail sorter – tracks applications from job emails
6. The map – career path to the goal role

## Files
- `app.py` – the website (Streamlit)
- `jobbank.py` – finds and downloads the newest Job Bank file
- `requirements.txt` – Python packages the website needs

Data: [Job Bank open data](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072), Open Government Licence – Canada.
