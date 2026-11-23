# India Blue-Team Employer Map

A list of **699 companies** that run, or hire for, cybersecurity defence (blue-team) work in **Bengaluru, Pune, Mumbai, Hyderabad, or remote/hybrid roles in India**. Blue-team work here means SOC, MDR, incident response/DFIR, threat intelligence, threat hunting, detection engineering, vulnerability management, IAM, cloud/OT security and GRC.

## Files
| File | What it is |
|---|---|
| `output/india_blue_team_companies.xlsx` | The main deliverable. Sheets: **Companies (focus cities)** (699 rows, filterable), **Other Indian cities** (6 rows), **Summary** (counts by city, category and revenue basis) |
| `output/india_blue_team_companies.csv` | The focus-city list as CSV |
| `data/*.txt` | Source data, pipe-delimited, one file per segment |
| `scripts/build.py` | Removes duplicates, filters to the focus cities and builds the CSV/XLSX: `python3 scripts/build.py` |

## Columns
Company · Category · Global HQ · India locations (all) · Yes/blank flags for Bengaluru / Pune / Mumbai / Hyderabad / Remote · Annual revenue · Revenue period · Revenue basis · Blue-team functions in India

## Coverage (focus list)
- **By city:** Bengaluru 484 · Mumbai 220 · Pune 188 · Hyderabad 173 · Remote/Hybrid 118 (a company can be in several cities)
- **By segment:** cybersecurity product vendors 134 · tech GCCs 110 · BFSI GCCs 83 · MSSP/MDR/cyber services 69 · IT services and consulting 63 · industrial/energy/auto GCCs 58 · healthcare/pharma GCCs 28 · retail/consumer GCCs 22 · Indian enterprises (banks, market infrastructure, insurers, fintech, internet, telecom, conglomerates, pharma, PSUs) 100 · Indian cyber product startups 32

## How to read the revenue figures
- **Revenue is the company's total annual revenue**, worldwide for multinationals, not India-only or security-only. The fiscal year is given in *Revenue period*.
- **Revenue basis = Reported** (446 rows): from annual reports or stock-exchange filings for the latest full fiscal year (mostly CY2024 or FY25). Figures are rounded.
- **Revenue basis = Estimate** (243 rows): private companies that don't publish results. These are directional estimates from press reports and data aggregators. **Spot checks against Inc42 and Entrackr found some of them off by 2x or more** (for example, Sequretek is ₹41 Cr, not the ₹100 Cr first estimated). The rows that were checked are corrected and marked as such.
- **MCA band:** only the Registrar of Companies revenue band is public.
- Indian banks show *total income*, and insurers show *gross premium* or *GDPI*, because those are their standard top-line figures.
- To get exact numbers for Indian private companies, look them up by CIN on the MCA portal (mca.gov.in), or use Tofler, Tracxn or Entrackr.

## How it was built and its limits
- The list was compiled from public company information: annual reports, careers pages, GCC announcements, NASSCOM/Zinnov GCC coverage and LinkedIn presence. A sample of Indian private-company revenues was then spot-checked online.
- **India locations show where the company has offices or teams with security roles.** They don't promise an open blue-team job today. Check current openings on the company's careers page or LinkedIn before applying or prospecting.
- For acquired companies, the list keeps the brand that still hires under its own name, with the parent shown in brackets. Examples: Paladion (Atos), CyberProof (UST), Mandiant (Google).
- Data is current to late 2025. GCC launches and acquisitions move quickly, so re-verify anything you'll make decisions on.

---

# Live hiring scan: blue-team roles posted in the last 15 days (Pune, Mumbai, Bengaluru)

`output/jobs/india_blue_team_hiring_last15days.xlsx` has three sheets:
- **Companies hiring**: companies with at least one SOC, detection engineering, threat intel/research, incident response, SIEM/XDR or security analyst role in Pune, Mumbai or Bengaluru **with a verifiable posting date within the last 15 days**.
- **All postings**: one row per posting, with its posting date and direct apply link.
- **Excluded companies**: every other company in the 699-company list, with the reason it was excluded and contact channels to check it yourself.

## Exclusion statuses
| Status | Meaning |
|---|---|
| Checked - only older postings | Matching roles exist in these cities, but none were posted in the last 15 days (the latest date is given) |
| Checked - roles in other cities only | Blue-team roles are open, but not in Pune, Mumbai or Bengaluru |
| Checked - no blue-team roles | The job board was read, and nothing matches SOC, detection, threat or IR |
| Checked - no recent match | The Workday career site was scanned with no match |
| Checked - unconfirmed | Scanned with 0 matches, but the connection kept dropping (JPMorgan, Oracle, Amazon) |
| Not verifiable automatically | The careers site has no public job API reachable from here. Hiring status is **unknown**, not "not hiring" |
| Out of city scope | The dataset shows no Pune, Mumbai or Bengaluru office |

## Contacts
Each row has (1) the company's job board or apply link, (2) a LinkedIn people search for that company's recruiters and talent-acquisition staff in security, and (3) a LinkedIn Jobs search limited to the last 15 days. Individual HR names, emails and phone numbers are **not** collected. They aren't available from public job APIs, scraping LinkedIn breaks its terms, and guessed addresses would be wrong. Open the LinkedIn links while logged in to find and message the right recruiter.

## Method
`scripts/jobs/ats_scan.py` reads companies' public job-board APIs (Greenhouse, Lever, Ashby, SmartRecruiters). `scripts/jobs/enterprise_scan.py` reads public Workday career-site APIs, Oracle Recruiting Cloud (JPMorgan, Oracle) and amazon.jobs. `scripts/jobs/build_jobs.py` builds the report. Role and city matching is in `scripts/jobs/rolefilter.py`. Re-run all three scripts to refresh. The 15-day window is counted back from the run date.
