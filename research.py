"""One-off research scrape: real student/part-time ads per job family, for a CV keyword bank.
Writes data/research.json (full page text per ad). Does not touch seen.json / latest.json."""
import json, random, re, time
from datetime import datetime, timezone
from pathlib import Path
import scan

QUERIES = json.loads((scan.ROOT / "research_queries.json").read_text(encoding="utf-8"))
SCOPE = re.compile(r"סטודנט|סטודנטית|student|intern|התמחות|חלקית|part.?time|junior|ג'וניור|ג׳וניור", re.I)
MAX_PER_FAMILY = 25

def main():
    log, out = [], {}
    for family, qs in QUERIES.items():
        cands = {}
        for q in qs:
            for site in ("alljobs", "drushim"):
                for item in scan.search_site(site, q, log):
                    if item["listTitle"] and not SCOPE.search(item["listTitle"]) and not SCOPE.search(q):
                        continue
                    cands.setdefault(item["key"], item)
                time.sleep(random.uniform(1.0, 2.0))
        jobs = []
        for c in list(cands.values())[:MAX_PER_FAMILY]:
            r = scan.get(c["url"])
            if r is not None and r.status_code == 200:
                title, text = scan.clean_text(r.text)
                c.update(pageTitle=title[:200], text=text[:6000])
                jobs.append(c)
            time.sleep(random.uniform(0.8, 1.5))
        out[family] = jobs
        log.append(f"{family}: {len(cands)} candidates, {len(jobs)} fetched")
    (scan.DATA / "research.json").write_text(json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(), "log": log, "families": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(l for l in log if ":" in l and "candidates" in l))

if __name__ == "__main__":
    main()
