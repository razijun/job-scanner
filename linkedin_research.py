"""One-off: fetch public LinkedIn job ads (guest pages, no login) for the CV keyword bank.
Writes data/linkedin_research.json."""
import json, re, time, random
from datetime import datetime, timezone
import scan

FAMILIES = {
    "product": ["product student", "product analyst student", "product intern", "competitive intelligence student"],
    "ba": ["business analyst student", "systems analyst student", "implementation specialist junior"],
    "om": ["operational excellence student", "process improvement student", "industrial engineering student"],
    "prodops": ["product operations student", "business operations student", "bizops student", "operations specialist student"],
    "ai": ["AI student", "AI evaluation", "AI operations student", "LLM evaluation", "AI trainer", "annotation specialist student"],
    "data": ["data analyst student", "BI student", "analyst student"],
    "ux": ["UX research student", "user research student", "UX student"],
    "pmo": ["PMO student", "PMO junior", "program manager student", "project coordinator student"],
    "cs": ["customer success student", "customer success operations student", "onboarding specialist student"],
    "research": ["student researcher", "research student"],
}
EXTRA_IDS = ["4488896753","4487927367","4485260367","4479851205","4484357071","4486959647","4476723009","4487758802",
             "4488860328","4481090234","4472492540","4479572060","4487909305","4474602338","4486698238","4452203216",
             "4462674334","4477988416","4484656032","4485513361","4483374347","4466865887","4348277466"]
SCOPE = re.compile(r"student|intern|part.?time|junior|graduate|סטודנט", re.I)
BASE = "https://www.linkedin.com/jobs-guest/jobs/api"

def strip(s):
    s = re.sub(r"<br\s*/?>|</(p|li|ul|div|h\d)>", "\n", s)
    s = re.sub(r"<li>", "• ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in (("&amp;", "&"), ("&#39;", "'"), ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">")):
        s = s.replace(a, b)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()

def main():
    log, fam_ids, seen = [], {}, set()
    for fam, qs in FAMILIES.items():
        fam_ids[fam] = []
        for q in qs:
            for start in (0, 10):
                r = scan.get(f"{BASE}/seeMoreJobPostings/search?keywords={scan.quote(q)}&location=Israel&start={start}")
                if r is None or r.status_code != 200:
                    log.append(f"search {q} {start}: {getattr(r,'status_code',None)}"); break
                for chunk in r.text.split("<li")[1:]:
                    m = re.search(r"jobPosting:(\d+)", chunk)
                    t = re.search(r"<h3[^>]*>([\s\S]*?)</h3>", chunk)
                    if not m or not t: continue
                    title = strip(t.group(1))
                    if m.group(1) in seen or not SCOPE.search(title): continue
                    seen.add(m.group(1)); fam_ids[fam].append(m.group(1))
                time.sleep(random.uniform(1.0, 2.0))
    fam_ids["extra"] = [i for i in EXTRA_IDS if i not in seen]
    jobs = {}
    for fam, ids in fam_ids.items():
        for jid in ids[:30]:
            r = scan.get(f"{BASE}/jobPosting/{jid}")
            if r is None or r.status_code != 200:
                log.append(f"job {jid}: {getattr(r,'status_code',None)}"); continue
            h = r.text
            g = lambda pat: strip((re.search(pat, h) or [None, ""])[1] if re.search(pat, h) else "")
            jobs[jid] = {"family": fam, "id": jid, "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                         "title": g(r"top-card-layout__title[^>]*>([\s\S]*?)</h2>"),
                         "company": g(r"topcard__org-name-link[^>]*>([\s\S]*?)</a>"),
                         "location": g(r"topcard__flavor--bullet[^>]*>([\s\S]*?)</span>"),
                         "posted": g(r"posted-time-ago__text[^>]*>([\s\S]*?)</span>"),
                         "criteria": g(r"description__job-criteria-list[^>]*>([\s\S]*?)</ul>"),
                         "description": g(r"show-more-less-html__markup[^>]*>([\s\S]*?)</div>")[:7000]}
            time.sleep(random.uniform(1.0, 2.0))
    out = {"generatedAt": datetime.now(timezone.utc).isoformat(), "log": log, "jobs": list(jobs.values())}
    (scan.DATA / "linkedin_research.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(jobs), "jobs;", len(log), "errors")

if __name__ == "__main__":
    main()
