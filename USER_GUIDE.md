# User Guide — Dream Hunt Dashboard

This guide walks you through every page of the Dream Hunt application, explains what each control does, and shares best practices for getting the most out of the AI scoring system.

---

## Table of Contents

- [Initial Setup](#initial-setup)
- [Launching the App](#launching-the-app)
- [Home Page](#home-page)
- [Scraper Page](#scraper-page)
- [AI Scoring Page](#ai-scoring-page)
- [Dashboard Page](#dashboard-page)
- [Best Practices](#best-practices)
- [FAQ](#faq)

---

## Initial Setup

Before running any scrapes you need to give the AI context about who you are.

### Step 1 — Add your resume

Place your current resume (PDF format) directly into the `data/` folder:

```
data/
└── Your_Resume.pdf
```

The AI reads this file to extract a semantic summary of your background. It uses the first ~300 words of text content, so make sure the most relevant experience and skills appear near the top of your resume. You can also upload the file from inside the app (AI Scoring page → Profile Context section).

### Step 2 — Configure your profile

Open `config/profile_config.json` (copy from `config/profile_config.example.json` if it does not exist yet) and fill in three key fields:

| Field | What to enter |
|---|---|
| `target_roles` | The exact job titles you are applying for (e.g. "Senior Data Analyst", "Analytics Engineer") |
| `min_experience_years` | Your total years of relevant work experience |
| `profile_keywords` | A flat list of your technical skills — tools, languages, platforms |

The more specific and complete these fields are, the more accurately the AI scores jobs against your profile.

---

## Launching the App

```bash
python run_dashboard.py
```

The terminal prints a system status summary (datasets found, last scrape time, skills count, top-matches queue) before opening the app at `http://localhost:8501`.

---

## Home Page

The landing page gives you an at-a-glance status view:

- **Datasets** — number of scraped job CSV files in `data/`
- **Last Scrape** — timestamp of the most recently modified job file
- **In Queue** — jobs scored ≥ 85 sitting in `data/top_matches.csv`

The "How it works" cards below summarise the four-step workflow. Use the top navigation bar to switch between pages.

---

## Scraper Page

### Search Configuration

| Control | Description |
|---|---|
| **Designation** *(required)* | The job title to search. Be specific — "Data Analyst" returns better results than "Data". |
| **Location** | City, state, or "India". Leave blank to search all of India. |
| **Experience (min years)** | Filters jobs requiring at least this many years. Set to 0 to disable. |
| **Salary (CTC)** | Pre-defined salary brackets. Using this filter significantly reduces result count — only set it if you have a firm requirement. |
| **Industry** | Sector filter (e.g. "IT - Software", "Banking / Financial Services"). Leave as "Any" for broader results. |
| **Time Period** | How far back to search. "Last 24 hours" is ideal for daily monitoring; "Any time" is best for a broad initial scan. |
| **How many jobs?** | Approximate target. Each page yields ~20 jobs; selecting 100 scrapes 5 pages. |
| **Work Mode** | Filter by On-site, Hybrid, or Remote. Multiple selections are allowed. |
| **Headless Browser** | When ON (default), Chrome runs silently in the background. Turn it OFF to watch the automation live — useful for debugging or when Naukri shows a CAPTCHA. |

### Running a scrape

Click **🚀 Start Scraping**. A live progress pipeline shows the five stages:

```
Initializing → Fetching → Parsing → AI Scoring → Saving
```

Each completed stage turns green. The log line below the pipeline shows the current URL and job count in real time.

When the scrape finishes you will see:
- Total jobs collected
- Top matches (score ≥ 85) and good matches (score ≥ 50)
- The filename the dataset was saved to

### Clear Scrape History

The **🗑️ Clear Scrape History** button deletes all `naukri_*.csv` files from `data/`. This resets the cross-run deduplication system, which means the next scrape will collect all jobs fresh — including ones previously seen.

---

## AI Scoring Page

This is where you spend most of your time.

### Filters

| Control | Effect |
|---|---|
| **Search** | Full-text search across job title, company name, and skills |
| **Min Score** | Slider to hide jobs below a score threshold |
| **Sort by** | AI Score descending/ascending or Company A-Z |
| **Company** | Multi-select filter |
| **Location** | Multi-select filter |
| **Work Mode** | Filters jobs mentioning Remote / Hybrid / On-site in description or location |

Active filters are shown as chips above the job feed. Changing any filter resets pagination to page 1.

### Job Cards

Each job card shows:

- **Score badge** — colour-coded circle (green ≥ 80, yellow ≥ 50, red < 50)
- **Match bar** — visual representation of the score
- **Meta pills** — location, experience range, posted date
- **Skill tags** — up to 12 skills extracted from the listing
- **Description excerpt** — the text Naukri shows on the search results page

Click the expander arrow to open a card and see:

- **Score breakdown** — separate bars for Skill Match, Title Relevance, Description Semantic, and Experience Fit
- **Full description**
- **Action buttons** — 👍 Good Fit, 👎 Bad Fit, View on Naukri →

### Providing feedback

Every time you click **👍 Good Fit** or **👎 Bad Fit**:

1. The job is saved to `data/applied_jobs.csv` or `data/rejected_jobs.csv`.
2. The card is marked with ✅ or ❌ so you know you have already rated it.
3. Once you have rated enough jobs (at least one on each side), click **🔄 Retrain AI Model** in the right panel to train the RandomForest model.

The more feedback you provide, the more personalised the scores become. Aim for 20–30 ratings before retraining for meaningful results.

### Profile Context

- **Experience slider** — adjust your years of experience. The AI uses this to calculate the experience fit signal. Changes save immediately to `config/profile_config.json`.
- **Resume upload** — drag and drop a PDF here as an alternative to placing it manually in `data/`. Use the ✕ button next to any listed PDF to delete it.

### Right panel

| Widget | Purpose |
|---|---|
| **Profile Intelligence** | Skill coverage ring — what % of all unique market skills your profile covers. Lists top missing skills. |
| **AI Model Status** | Shows whether the ML model is loaded, how many samples it was trained on, and when it was last trained. |
| **Retrain AI Model** | Triggers `JobAIModel.train()`. On success, clears the Streamlit cache and re-scores all jobs with the updated model. |
| **Upskill Radar** | The top 5 skills appearing in job listings that are not in your profile — sorted by listing frequency. |
| **Top Matches** | A count of jobs in `data/top_matches.csv` with a quick preview button. |

### Skills Management

At the bottom of the page:

- **Add skill** — type one skill or a comma-separated list (e.g. `dbt, Snowflake, Airflow`) and click **➕ Add Skill**.
- **Remove skill** — click any skill tag in the cloud to delete it.

Changes are saved instantly to `config/profile_config.json`. Reload the AI Scoring page (or click Retrain) to see the updated scores.

---

## Dashboard Page

A read-only analytics view of the latest job dataset.

### Score Distribution

A horizontal bar chart breaking jobs into four score bands:

| Band | Score Range |
|---|---|
| Low | < 50 |
| Mid | 50–69 |
| Good | 70–84 |
| Top | 85+ |

### Your Profile vs The Market

Two side-by-side panels:

- **Skill Coverage** — a donut chart showing the % of unique market skills you cover, with a list of the top skills you are missing (learn these to improve your scores).
- **Top Matched Skills** — your skills that appear most frequently in the current dataset, with frequency bars.

### Hiring Trends

- **Top Companies** — the 10 companies posting the most jobs for your search.
- **Top Locations** — the 10 cities with the most listings.

### Experience Fit

A bar chart of minimum experience requirements across all jobs, with a dashed red line marking your configured experience level. This tells you at a glance how many jobs are slightly above or below your range.

### AI Feedback Summary & Raw Data

- **AI Feedback Summary** — counts of Good Fit / Bad Fit ratings and current model status.
- **Raw Data** — an interactive table of all scored jobs. Use **Download Full Dataset** to export a CSV with all AI signals (AI_Score, Score_Skill, Score_Title, Score_Desc, Score_Exp).

---

## Best Practices

**Scrape daily with "Last 24 hours".**  
Job boards move fast. A daily scrape with the 24-hour filter keeps your feed fresh and prevents missing short-listed roles.

**Set specific target roles.**  
`target_roles: ["Senior Data Analyst"]` scores more accurately than `["Analyst"]`. The title relevance signal compares job titles against your target list using semantic similarity.

**Rate jobs consistently.**  
The ML model learns your preferences from the pattern of your ratings, not just the score. Rate at least 20–30 jobs before retraining for meaningful personalisation.

**Update skills after learning something new.**  
Adding a skill (e.g. `dbt`, `Snowflake`) to your profile immediately improves your skill-match score for jobs requiring that skill — no retraining needed.

**Use the Upskill Radar to guide learning.**  
The radar shows which skills appear most in your target job market but are absent from your profile. Prioritise the top 2–3 for maximum marketability.

**Keep the resume PDF current.**  
The description semantic signal compares job descriptions against your resume text. An outdated resume degrades this signal. Re-upload after major profile changes.

---

## FAQ

**Q: Can I scrape multiple roles at once?**  
A: Not from a single run. Run separate scrapes for each role (e.g. "Data Analyst", "Business Analyst"). The dashboard always loads the most recently modified dataset.

**Q: My scrape returned 0 jobs — what happened?**  
A: Most likely Naukri served a CAPTCHA or the selectors changed. Try running with Headless OFF to watch the browser, and check `logs/app.log` for error details.

**Q: The AI scores seem off — is something wrong?**  
A: Check that `config/profile_config.json` has at least 5–10 skills in `profile_keywords` and that your `target_roles` match the kinds of jobs you are seeing. Also confirm your resume PDF is in `data/` and is text-based (not a scanned image).

**Q: How do I reset the ML model and start fresh?**  
A: Delete `data/job_ai_model.pkl`, `data/applied_jobs.csv`, and `data/rejected_jobs.csv`. The app will revert to the baseline scoring mode.

**Q: Why do some jobs show the same score across multiple scrapes?**  
A: The baseline score is deterministic — the same job with the same profile config always produces the same score. Scores vary after you retrain the ML model with new feedback.
