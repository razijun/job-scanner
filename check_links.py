"""One-off: check whether saved board jobs are still live. Writes data/linkcheck.json."""
import json, re, time
import scan
from bs4 import BeautifulSoup
LI = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
out = []
for key, url in json.loads(open("check_urls.json", encoding="utf-8").read()).items():
    target = LI + re.search(r"/view/(\d+)", url).group(1) if "linkedin.com/jobs/view" in url else url
    r = scan.get(target)
    rec = {"key": key, "url": url, "status": getattr(r, "status_code", None), "final": getattr(r, "url", None)}
    if r is not None:
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript"]): t.decompose()
        txt = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        rec["title"] = (soup.title.string or "").strip()[:150] if soup.title else ""
        rec["len"] = len(txt)
        rec["head"] = txt[:400]
        rec["closed"] = bool(re.search(r"No longer accepting applications|המשרה אינה פעילה|המשרה לא נמצאה|משרה זו אינה|הוסרה|לא קיימת|not found|expired", txt, re.I))
    out.append(rec)
    time.sleep(5 if "linkedin" in target else 1.5)
json.dump(out, open("data/linkcheck.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
