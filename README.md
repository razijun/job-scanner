# job-scanner

Daily scraper for public job ads (JobMaster, AllJobs, Drushim) that feeds a personal job-matching bot.
GitHub Actions runs `scan.py` every morning and commits `data/latest.json` (new listings with their page text).
Only public job ads and search terms are stored here.
