"""Daily job-board scraper for the job scanner.

Runs on GitHub Actions (open internet), reads the search pages of JobMaster,
AllJobs and Drushim, opens every new listing and stores its text in
data/latest.json. The Claude scan task reads that file and does the matching.
No personal data is stored here: only public job ads and the search terms.
"""
import json
import random
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CONFIG = json.loads((ROOT / "queries.json").read_text(encoding="utf-8"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "he-IL,he;q=0.9,en;q=0.8"})

MAX_JOB_PAGES = 220   # per run, across all sites
TEXT_LIMIT = 3500     # characters kept from each job page
SEEN_DAYS = 45        # forget keys after this many days

SITES = {
    "jobmaster": {
        "prefix": "jm",
        "search": lambda q: f"https://www.jobmaster.co.il/jobs/q-{quote(q)}/",
        "key_re": re.compile(r"checknum\.asp\?key=(\d+)", re.I),
        "job_url": lambda k: f"https://www.jobmaster.co.il/jobs/checknum.asp?key={k}",
    },
    "alljobs": {
        "prefix": "aj",
        "search": lambda q: f"https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&freetxt={quote(q)}",
        "key_re": re.compile(r"JobID=(\d+)", re.I),
        "job_url": lambda k: f"https://www.alljobs.co.il/Search/UploadSingle.aspx?JobID={k}",
    },
    "drushim": {
        "prefix": "dr",
        "search": lambda q: f"https://www.drushim.co.il/jobs/search/{quote(q)}/",
        "key_re": re.compile(r"/job/(\d+)/([0-9a-f]+)", re.I),
        "job_url": None,  # built from the full link (needs the hash part)
    },
}


def get(url):
    for attempt in range(2):
        try:
            r = SESSION.get(url, timeout=25)
            return r
        except requests.RequestException:
            time.sleep(3 + attempt * 3)
    return None


def clean_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return title, text


WARMED = set()


def warm_up(site):
    """Visit the site's home page once so it sets its session cookies (JobMaster hides results without them)."""
    if site in WARMED:
        return
    WARMED.add(site)
    home = {"jobmaster": "https://www.jobmaster.co.il/", "alljobs": "https://www.alljobs.co.il/",
            "drushim": "https://www.drushim.co.il/"}[site]
    get(home)
    SESSION.headers["Referer"] = home


def search_site(site, query, log):
    cfg = SITES[site]
    warm_up(site)
    url = cfg["search"](query)
    r = get(url)
    if r is None or r.status_code != 200:
        log.append(f"{site} '{query}': search failed ({getattr(r, 'status_code', 'no response')})")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    if site == "jobmaster" and not cfg["key_re"].search(r.text):
        DATA.mkdir(exist_ok=True)
        (DATA / "debug-jobmaster.html").write_text(r.text[:60000], encoding="utf-8")
        log.append(f"jobmaster debug: status {r.status_code}, final url {r.url}, len {len(r.text)}")
    found = {}
    for a in soup.find_all("a", href=True):
        m = cfg["key_re"].search(a["href"])
        if not m:
            continue
        key = cfg["prefix"] + m.group(1)
        if key in found:
            continue
        label = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        if site == "drushim":
            job_url = urljoin("https://www.drushim.co.il", f"/job/{m.group(1)}/{m.group(2)}/")
        else:
            job_url = cfg["job_url"](m.group(1))
        found[key] = {"key": key, "site": site, "url": job_url, "listTitle": label[:200], "query": query}
    log.append(f"{site} '{query}': {len(found)} results")
    return list(found.values())


def main():
    DATA.mkdir(exist_ok=True)
    seen_path = DATA / "seen.json"
    seen = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.exists() else {}
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=SEEN_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}

    log = []
    candidates = {}
    for person, queries in CONFIG["queries"].items():
        for site, qs in queries.items():
            for q in qs:
                for item in search_site(site, q, log):
                    entry = candidates.setdefault(item["key"], {**item, "people": []})
                    if person not in entry["people"]:
                        entry["people"].append(person)
                time.sleep(random.uniform(1.0, 2.0))

    relevant = re.compile(CONFIG["titleFilter"], re.I)
    new = [c for k, c in candidates.items() if k not in seen and (not c["listTitle"] or relevant.search(c["listTitle"]))]
    log.append(f"after title filter: {len(new)} new of {len(candidates)}")
    jobs = []
    for c in new[:MAX_JOB_PAGES]:
        r = get(c["url"])
        if r is None:
            c.update(ok=False, status=None)
        else:
            title, text = clean_text(r.text)
            c.update(ok=r.status_code == 200, status=r.status_code, pageTitle=title[:200], text=text[:TEXT_LIMIT])
        c["fetchedAt"] = now.isoformat()
        jobs.append(c)
        seen[c["key"]] = now.isoformat()
        time.sleep(random.uniform(0.8, 1.6))

    out = {
        "generatedAt": now.isoformat(),
        "searchResults": len(candidates),
        "newJobs": len(jobs),
        "skippedOverLimit": max(0, len(new) - MAX_JOB_PAGES),
        "log": log,
        "jobs": jobs,
    }
    (DATA / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"search results: {len(candidates)}, new: {len(jobs)}")
    print("\n".join(log))


if __name__ == "__main__":
    main()
