"""Work-permit / immigration requirements.

Two parts of the project scope:
  1. Read what a job description says about who can apply (English and French).
  2. Ask the applicant their status once, then flag every job:
       ✅ can apply   ⚠️ check the posting   ❌ not eligible as written

Job Bank's open-data file has no field for this, so Job Bank jobs are marked
"not stated" until we have their full text (email alerts, pasted jobs).
"""
import re

NOT_STATED = "Not stated"
JOB_BANK_NOTE = "Not in Job Bank's data – check the posting"

# Order matters: the first rule that matches wins (most restrictive first).
RULES = [
    ("Citizens or permanent residents only", [
        r"(must|need to|required to) (be|hold) (a )?canadian citizen",
        r"canadian citizens?(hip)? (or|and|/) permanent residen\w*( status)? (only|is required|are required|required)",
        r"(only|restricted to) canadian citizens",
        r"(security|secret|reliability) clearance",
        r"citoyen(ne)?s? canadien(ne)?s? (ou|et) r[ée]sident(e)?s? permanent(e)?s? (seulement|uniquement)",
        r"(doit|devez) [êe]tre citoyen",
    ]),
    ("No sponsorship offered", [
        r"(not|unable to|cannot|can't|won't|will not|do not|does not)\s+(be able to\s+)?(offer|provide|support|sponsor)\w*\s+(visa|work permit|immigration|sponsorship)",
        r"no (visa |immigration |work permit )?sponsorship",
        r"sponsorship (is )?not (available|offered|provided)",
        r"without (the need for )?(current or future )?sponsorship",
        r"(aucun|pas de) parrainage",
        r"ne (pouvons|peut) pas (offrir|parrainer)",
    ]),
    ("Sponsorship / LMIA possible", [
        r"(visa|immigration|work permit) sponsorship (is )?(available|offered|provided|possible)",
        r"(will|can|may|able to) sponsor",
        r"\blmia\b",
        r"labou?r market impact assessment",
        r"temporary foreign worker",
        r"\beimt\b",
        r"[ée]tude d'impact sur le march[ée] du travail",
        r"travailleurs? [ée]trangers? temporaires?",
        r"parrainage (disponible|offert|possible)",
    ]),
    ("Work permit holders welcome", [
        r"(valid|open|current) (canadian )?work permit",
        r"temporary residents? (of canada )?with a valid work permit",
        r"work permit holders",
        r"permis de travail (valide|ouvert)",
    ]),
    ("Must be legally allowed to work in Canada", [
        r"(legally )?(eligible|entitled|authori[sz]ed|permitted|able) to work in canada",
        r"right to work in canada",
        r"(l[ée]galement )?(autoris[ée]e?|admissible) [àa] travailler au canada",
        r"permis de travail",
        r"work permit",
    ]),
]
_COMPILED = [(label, [re.compile(p, re.I) for p in pats]) for label, pats in RULES]


def requirement(text):
    """What the job description says about who can apply."""
    t = text or ""
    for label, pats in _COMPILED:
        if any(p.search(t) for p in pats):
            return label
    return NOT_STATED


STATUSES = [
    "Prefer not to say",
    "Canadian citizen",
    "Permanent resident",
    "Open work permit",
    "Employer-specific work permit",
    "Study permit (can work part-time)",
    "No permit yet – I need sponsorship",
]


def fit(status, req):
    """Return (icon, reason) for one applicant status and one job requirement."""
    if status == "Prefer not to say":
        return "", ""
    if status in ("Canadian citizen", "Permanent resident"):
        return "✅", "You can apply."
    if req == "Citizens or permanent residents only":
        return "❌", "This job is only for Canadian citizens or permanent residents."
    if status == "Open work permit":
        if req == JOB_BANK_NOTE:
            return "⚠️", "Job Bank's data doesn't say who can apply. Most jobs accept an open work permit – check the posting."
        return "✅", "An open work permit lets you work for this employer."
    if status == "Employer-specific work permit":
        if req == "Sponsorship / LMIA possible":
            return "✅", "This employer mentions an LMIA or sponsorship, which you would need to change employers."
        if req == "No sponsorship offered":
            return "❌", "Your permit is tied to one employer and this job offers no sponsorship."
        return "⚠️", "Your permit is tied to one employer. A new employer would usually need an LMIA – ask before applying."
    if status == "Study permit (can work part-time)":
        if req == "No sponsorship offered":
            return "⚠️", "You can work part-time with a study permit, but the job offers no sponsorship later."
        return "⚠️", "A study permit limits your hours – check that the job's hours fit."
    if status == "No permit yet – I need sponsorship":
        if req == "Sponsorship / LMIA possible":
            return "✅", "This job mentions sponsorship or an LMIA."
        if req in ("No sponsorship offered", "Must be legally allowed to work in Canada", "Work permit holders welcome"):
            return "❌", "This job asks for people already allowed to work in Canada."
        return "⚠️", "Not stated – ask the employer whether they can sponsor."
    return "", ""
