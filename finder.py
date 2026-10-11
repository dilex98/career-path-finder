"""Company finder - discovers which Canadian employers use an open hiring system.

Hiring systems have no public directory of their customers, so we start from a
list of Canadian employer names, guess their board name on each open system
("Coveo" -> "coveo"), and ask the official public feed. A company is kept only
if the feed answers AND it has at least one job located in Canada.

The list below is a starting point: well-known Canadian employers (Montréal and
Québec first, then the rest of Canada) across tech, finance, retail, health,
gaming, transport, manufacturing and services. Anyone on the team can add names.
Results are rechecked automatically (the app keeps them for 7 days).
"""
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import feeds

CANDIDATES = """
Coveo, Lightspeed, Nuvei, SSENSE, Hopper, Dialogue, Mila, Poka, MaintainX, Moment Factory, Behaviour Interactive,
Ubisoft, Eidos Montreal, WB Games Montreal, Unity, Element AI, Sonder, Breather, Busbud, Frank And Oak, Aldo, Simons,
Dollarama, Couche-Tard, Metro, Saputo, Lassonde, Cascades, CAE, Bombardier, Alstom, Desjardins, National Bank,
Banque Nationale, Intact, Beneva, iA Financial, Mouvement Desjardins, Videotron, Bell, Cogeco, Telus, Rogers,
Optimum Technologies, Plusgrade, Felix Health, Petal, Flinks, Mogo, Wealthsimple, Questrade, KOHO, Neo Financial,
Clearco, Borrowell, Nesto, Properly, League, Wave, FreshBooks, Ada, Cohere, 1Password, Shopify, Wattpad, Faire,
Kijiji, Thinkific, Hootsuite, Clio, Benevity, Jobber, ApplyBoard, Vena Solutions, Dapper Labs, Ritual, Hockeystack,
D2L, Vidyard, Top Hat, Tulip, Ecobee, Kinaxis, Ceridian, Dayforce, OpenText, Magnet Forensics, Absolute Software,
Trulioo, Galvanize, Visier, Unbounce, Bench, Procurify, Dooly, Later, Article, Lululemon, Aritzia, Roots, Canada Goose,
Indigo, Sephora, Mejuri, Frank And Oak, Tim Hortons, Restaurant Brands International, Cineplex, Air Canada, Air Transat,
WestJet, Porter, Flair Airlines, CN, CPKC, Purolator, Intelcom, GoBolt, Uber, Lyft, DoorDash, Instacart, Airbnb,
Stripe, Spotify, Microsoft, Google, Amazon, Meta, Salesforce, SAP, Ericsson, Nokia, Ciena, Samsung, Sony, EA,
Electronic Arts, Square Enix, Keywords Studios, Gameloft, Epic Games, Riot Games, Ludia, Bioware, Ubisoft Toronto,
Mphasis, CGI, Alithya, Levio, Nventive, Spiria, Momentum Technologies, Sigma Software, EXFO, Genetec, Matrox, Hexagon,
Valsoft, Constellation Software, Mitel, Nuance, Sanofi, Pfizer, Novartis, AbbVie, Merck, Medtronic, Stryker, Dentalcorp,
Maple, Tia Health, Jane, PocketHealth, Kids Help Phone, Moneris, Paystone, Nuvei, Interac, Mastercard, Visa, Amex,
TD, RBC, BMO, Scotiabank, CIBC, Manulife, Sun Life, Canada Life, Great West Life, Definity, Aviva, Co-operators,
Loblaw, Sobeys, Walmart, Costco, Best Buy, Staples, Home Depot, Canadian Tire, Rona, IKEA, Decathlon, Sport Chek,
Hudson's Bay, Holt Renfrew, La Maison Simons, Pharmaprix, Jean Coutu, Familiprix, Uniprix, Bauer, CCM, BRP, Prevost,
Lion Electric, Taiga Motors, Hydro-Quebec, Hydro One, Enbridge, TC Energy, Suncor, Cenovus, Fortis, Brookfield,
Ivanhoe Cambridge, Cadillac Fairview, Oxford Properties, Colliers, CBRE, JLL, WSP, SNC-Lavalin, AtkinsRealis,
Stantec, Pomerleau, EllisDon, PCL, Deloitte, KPMG, EY, PwC, BDO, Raymond Chabot, MNP, Accenture, Capgemini,
Keyloop, Alimentiv, Immiland, EQ Bank, Kong, Wealthsimple, Dialogue Health, Hootsuite, Clearbanc, Applydigital,
Achievers, Rangle, Xanadu, Sanctuary AI, Waabi, Ada Support, Layer 6, Borealis AI, Vector Institute, Mila Quebec,
Botpress, Heyday, Alan, Workleap, GSoft, Officevibe, Sharegate, Lightspeed Commerce, Potloc, Hivestack, Vention,
AlayaCare, Classcraft, Workland, Mirego, Bciti, Unito, Missive, Agendrix, LeddarTech, Kinova, Robotiq, Stornoway,
Aubainerie, Amilia, Parent, EyeCarePro, RBR, FER-PAL Infrastructure, Thinkific, Jobber, Faire, Fullscript, FIG Financial,
Cybera, Renewal by Andersen, Versaterm, Quadbridge, StackAdapt, CapIntel, Knix, RioCan, Swapcard, Mistplay, Potloc,
"""

# Board names a company is likely to use, e.g. "Lightspeed Commerce" -> lightspeedcommerce, lightspeed-commerce
def slugs(name):
    base = re.sub(r"[^a-z0-9 ]", "", name.lower().replace("&", "and").replace("'", "")).split()
    out = ["".join(base), "-".join(base)]
    return list(dict.fromkeys(s for s in out if s))


def names():
    return list(dict.fromkeys(n.strip() for n in CANDIDATES.replace("\n", " ").split(",") if n.strip()))


def _check(job):
    """job = (system, board name, company name): return the company if it has jobs in Canada."""
    ats, token, name = job
    try:
        rows = [r for r in feeds.FETCHERS[ats](token, name, details=False) if feeds.in_canada(r)]
        return (ats, token, name, len(rows)) if rows else None
    except feeds.NotFound:
        return None
    except Exception:
        return "busy"  # the system was busy: not the same as "not there"


def find(extra_names=()):
    """Try every name on every open system. Returns a table of companies found with jobs in Canada."""
    known = {(a, t.lower()) for a, t, _ in feeds.COMPANIES}
    tries = [(ats, slug, name) for name in names() + list(extra_names) for slug in slugs(name)
             for ats in feeds.FETCHERS if (ats, slug) not in known]
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(_check, tries))
    found = [r for r in answers if r and r != "busy"]
    busy = sum(r == "busy" for r in answers)
    df = pd.DataFrame(found, columns=["system", "board", "company", "jobs in Canada"])
    df["busy checks"], df["checks"] = busy, len(tries)  # kept as columns so they survive caching
    # one row per company per system (both slug spellings can answer)
    return (df.sort_values("jobs in Canada", ascending=False)
              .drop_duplicates(subset=["system", "board"]).reset_index(drop=True))
