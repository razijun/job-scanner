"""One-off second pass (slower, to avoid 429): student/part-time LinkedIn ads not fetched in the first pass.
Writes data/linkedin_research2.json."""
import json, re, time, random
from datetime import datetime, timezone
import scan
from linkedin_research import FAMILIES, EXTRA_IDS, BASE, strip

STRICT = re.compile(r"student|intern|part.?time|סטודנט", re.I)
ORDER = ["product", "ux", "data", "pmo", "cs", "ai", "prodops", "ba", "om", "research"]

def fetch(jid, fam, log):
    r = scan.get(f"{BASE}/jobPosting/{jid}")
    if r is None or r.status_code != 200:
        log.append(f"job {jid}: {getattr(r,'status_code',None)}"); return None
    h = r.text
    g = lambda pat: strip(re.search(pat, h).group(1)) if re.search(pat, h) else ""
    return {"family": fam, "id": jid, "url": f"https://www.linkedin.com/jobs/view/{jid}/",
            "title": g(r"top-card-layout__title[^>]*>([\s\S]*?)</h2>"),
            "company": g(r"topcard__org-name-link[^>]*>([\s\S]*?)</a>"),
            "location": g(r"topcard__flavor--bullet[^>]*>([\s\S]*?)</span>"),
            "posted": g(r"posted-time-ago__text[^>]*>([\s\S]*?)</span>"),
            "criteria": g(r"description__job-criteria-list[^>]*>([\s\S]*?)</ul>"),
            "description": g(r"show-more-less-html__markup[^>]*>([\s\S]*?)</div>")[:7000]}

def main():
    have = {j["id"] for j in json.loads((scan.DATA / "linkedin_research.json").read_text())["jobs"]}
    log, todo = [], [("extra", i) for i in EXTRA_IDS if i not in have]
    seen = set(have) | {i for _, i in todo}
    for fam in ORDER:
        for q in FAMILIES[fam]:
            r = scan.get(f"{BASE}/seeMoreJobPostings/search?keywords={scan.quote(q)}&location=Israel&start=0")
            if r is None or r.status_code != 200:
                log.append(f"search {q}: {getattr(r,'status_code',None)}"); time.sleep(20); continue
            for chunk in r.text.split("<li")[1:]:
                m = re.search(r"jobPosting:(\d+)", chunk); t = re.search(r"<h3[^>]*>([\s\S]*?)</h3>", chunk)
                if m and t and m.group(1) not in seen and STRICT.search(strip(t.group(1))):
                    seen.add(m.group(1)); todo.append((fam, m.group(1)))
            time.sleep(random.uniform(3, 5))
    jobs = []
    for fam, jid in todo[:70]:
        j = fetch(jid, fam, log)
        if j: jobs.append(j)
        else: time.sleep(25)
        time.sleep(random.uniform(4, 7))
    out = {"generatedAt": datetime.now(timezone.utc).isoformat(), "log": log, "jobs": jobs}
    (scan.DATA / "linkedin_research2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(jobs), "jobs;", len(log), "errors")

if __name__ == "__main__":
    main()
