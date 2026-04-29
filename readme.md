# Dream Hunt — AI-Powered Job Intelligence Platform

> Automate job discovery on Naukri.com, score every listing against your resume using a 4-signal AI engine, and track market trends — all from a single dashboard.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-4.x-43B02A?logo=selenium&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.x-F7931E?logo=scikit-learn&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [CLI Usage](#cli-usage)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Dream Hunt is a local-first job intelligence tool that connects three layers:

1. **Scraper** — A Selenium-based headless browser that fetches structured job listings from Naukri.com, bypassing anti-bot mechanisms via stealth configuration and user-agent spoofing.
2. **AI Scoring Engine** — A deterministic 4-signal baseline model (skills, title relevance, description semantics, experience fit) that optionally blends with a user-trained RandomForest classifier as feedback accumulates.
3. **Streamlit Dashboard** — An "Ethereal Glass" UI built with custom CSS that renders job feeds, score breakdowns, market analytics, and upskill recommendations.

All communication between components happens via the filesystem (`data/` CSVs), keeping each layer independently testable and crash-safe.

---

## Key Features

| Feature | Description |
|---|---|
| **Headless Scraping** | Chrome WebDriver with stealth options; configurable headless/visible toggle |
| **Cross-run Deduplication** | New scrapes skip URLs already present in previous `data/*.csv` files |
| **4-Signal AI Score** | Skill match (35%) · Title relevance (25%) · Description semantic (25%) · Experience fit (15%) |
| **ML Feedback Loop** | Rate jobs Good/Bad Fit → trains a RandomForest → blended 60/40 with baseline |
| **Score Explainability** | Expandable "Match Intelligence" panel shows per-signal breakdown for every job |
| **Upskill Radar** | Identifies market skills absent from your profile, sorted by job frequency |
| **Profile Intelligence** | Skill coverage ring: your skills vs. total unique skills in the current dataset |
| **Hiring Trends** | Top companies and locations by listing count, rendered as interactive Plotly charts |
| **Auto Top-Matches Queue** | Jobs scoring ≥ 85 are automatically appended to `data/top_matches.csv` |
| **CLI Mode** | Full scraper functionality accessible via `python -m src.scraper.scraper_cli` |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | 3.11 recommended |
| Google Chrome | Latest stable | Must be installed system-wide |
| ChromeDriver | Auto-managed | Installed automatically by `webdriver-manager` |
| pip | 23+ | `pip install --upgrade pip` |

> **macOS users**: Chrome is detected from its default install path. No additional setup needed.
>
> **Linux users**: Install Chrome via `apt` or your distro's package manager before running.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/dream-hunt.git
cd dream-hunt
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The first run will download the `all-MiniLM-L6-v2` SentenceTransformer model (~80 MB) from HuggingFace. Subsequent runs use a cached copy.

---

## Configuration

### Profile config

Copy the example template and fill in your details:

```bash
cp config/profile_config.example.json config/profile_config.json
```

Edit `config/profile_config.json`:

```jsonc
{
  "min_experience_years": 3,          // your total years of experience
  "target_roles": [                   // job titles you are targeting
    "Data Analyst",
    "Senior Data Analyst",
    "Analytics Engineer"
  ],
  "profile_keywords": [               // your technical skills (used for skill-match scoring)
    "Python", "SQL", "Power BI", "Tableau", "Excel",
    "Data Visualization", "ETL", "Data Modeling", "Pandas"
  ],
  "scraper_defaults": {               // pre-filled values in the Scraper UI
    "designation": "Data Analyst",
    "location": "India",
    "experience": 3,
    "salary": "Any",
    "industry": "Any",
    "time_period": "Last 3 days",
    "max_jobs": 100,
    "work_mode": [],
    "headless": true
  }
}
```

> **Tip:** You can also manage skills directly from the AI Scoring page in the UI — changes are written back to this file in real time.

### Resume (optional but recommended)

Place your resume PDF in the `data/` folder:

```
data/
└── Your_Resume.pdf
```

The AI reads the first ~300 words of the PDF to build a semantic profile for description matching. Without a PDF, it falls back to your `profile_keywords` list.

---

## Running the App

```bash
python run_dashboard.py
```

This prints a system status summary and launches Streamlit at `http://localhost:8501`.

The app has four pages accessible via the top navigation bar:

| Page | Purpose |
|---|---|
| **Home** | System status, dataset count, how-it-works overview |
| **🕸️ Scraper** | Configure search parameters and run a live scrape |
| **🧠 AI Scoring** | Browse AI-ranked jobs, provide feedback, manage skills |
| **📊 Dashboard** | Market analytics, skill coverage, hiring trends, raw data export |

---

## How It Works

### Scraping pipeline

```
Start Scraping
     │
     ▼
[1] Initializing  →  Chrome WebDriver launched with stealth options
     │
     ▼
[2] Fetching      →  Pages loaded with random delays (2–4s); up to 2 retries per page
     │
     ▼
[3] Parsing       →  CSS selectors extract Title, Company, Location, Experience,
     │               Description, Skills, Posted date, Job URL
     ▼
[4] AI Scoring    →  JobAIModel.predict_scores() scores each job 0–100
     │
     ▼
[5] Saving        →  Deduplicated CSV written to data/; top-match queue updated
```

### AI scoring model

The `JobAIModel` in `src/ai/ai_opportunity_finder.py` computes a weighted score from four independent signals:

| Signal | Weight | Method |
|---|---|---|
| **Skill Match** | 35% | Fuzzy substring match: your `profile_keywords` vs. job's `Skills` field |
| **Title Relevance** | 25% | Cosine similarity via `all-MiniLM-L6-v2` (SentenceTransformer): job title vs. `target_roles` |
| **Description Semantic** | 25% | Cosine similarity: job description vs. first 300 words of your resume PDF |
| **Experience Fit** | 15% | Smooth decay function: 100 if within range, –12 pts per year outside |

When you rate jobs Good Fit / Bad Fit and click **Retrain AI Model**, a `RandomForestClassifier` trains on the combined feature matrix (text embeddings + experience + signal scores). Subsequent predictions blend ML probability (60%) with the deterministic baseline (40%).

### Feedback loop

```
Rate job 👍/👎
     │
     ├──► data/applied_jobs.csv  (label = 1)
     └──► data/rejected_jobs.csv (label = 0)
              │
              ▼
       Retrain AI Model
              │
              ▼
       data/job_ai_model.pkl  (RandomForest + metadata)
              │
              ▼
   predict_scores() → 60% ML + 40% baseline blend
```

---

## Project Structure

```
dream-hunt/
├── config/
│   ├── profile_config.json          # Your profile (gitignored)
│   └── profile_config.example.json  # Template to copy from
├── data/                            # All runtime data (gitignored)
│   ├── Your_Resume.pdf              # Resume for semantic matching
│   ├── naukri_<role>_<date>.csv     # Raw scraped job datasets
│   ├── applied_jobs.csv             # Good Fit feedback
│   ├── rejected_jobs.csv            # Bad Fit feedback
│   ├── top_matches.csv              # Auto-queued jobs scoring ≥ 85
│   ├── job_ai_model.pkl             # Trained RandomForest model
│   └── .scrape_session.json         # Live session status (UI polling)
├── logs/
│   └── app.log                      # Centralised log output
├── src/
│   ├── ai/
│   │   └── ai_opportunity_finder.py # JobAIModel: scoring, training, recommendations
│   ├── scraper/
│   │   └── scraper_cli.py           # NaukriScraper: Selenium + URL builder + CLI
│   ├── dashboard/
│   │   ├── app.py                   # Streamlit entry point (Home page)
│   │   ├── design.py                # "Ethereal Glass" CSS framework + HTML components
│   │   └── pages/
│   │       ├── 1_🕸️_Scraper.py
│   │       ├── 2_🧠_AI_Scoring.py
│   │       └── 3_📊_Dashboard.py
│   └── utils/
│       └── logger.py                # Centralised logging setup
├── tests/
│   ├── test_scraper.py
│   └── test_ai_model.py
├── run_dashboard.py                 # Launcher script with status summary
├── requirements.txt
└── README.md
```

---

## CLI Usage

Run the scraper without the UI:

```bash
python -m src.scraper.scraper_cli \
  --role "Data Analyst" \
  --location "Bangalore" \
  --pages 3 \
  --days 7 \
  --experience 3 \
  --max-jobs 60 \
  --output data/my_scrape.csv
```

All flags are optional — the CLI prompts for role and location if omitted.

| Flag | Default | Description |
|---|---|---|
| `--role` | (prompt) | Job title to search |
| `--location` | (prompt) | City, state, or "India" |
| `--pages` | 1 | Number of result pages to scrape |
| `--days` | 0 (any time) | Only jobs posted in the last N days |
| `--experience` | None | Minimum experience filter (years) |
| `--salary` | None | Salary bucket (e.g. "6 - 10 Lakhs") |
| `--industry` | None | Industry name from supported list |
| `--work-mode` | None | One or more of: On-site, Hybrid, Remote |
| `--max-jobs` | None | Cap total jobs collected |
| `--output` | Auto-timestamped | Output CSV path |
| `--visible` | False | Show Chrome browser window |

---

## Troubleshooting

### ChromeDriver version mismatch

```
SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version X
```

**Fix:** `webdriver-manager` should handle this automatically. If it doesn't, update it:

```bash
pip install --upgrade webdriver-manager
```

### SentenceTransformer download fails

The model downloads on first run from HuggingFace. If you are behind a proxy or firewall:

```bash
export HTTPS_PROXY=http://your-proxy:port
python run_dashboard.py
```

Or pre-download the model and set `SENTENCE_TRANSFORMERS_HOME` to point to the local cache directory.

### No jobs found / CAPTCHA

Naukri.com occasionally serves a CAPTCHA challenge. Symptoms: scraper completes but returns 0 jobs.

- Uncheck **Headless Browser** in the UI (or pass `--visible` in CLI) to watch the browser and solve any CAPTCHA manually.
- Reduce pages to 1–2.
- The scraper already applies a 2–4s random delay between requests; increasing this further in `scraper_cli.py` can help.

### Streamlit shows "No job data found"

Ensure at least one `naukri_*.csv` file exists in `data/`. Run a scrape first from the Scraper page.

### ML model not activating after retraining

The model requires at least **one job on each side** (one Good Fit and one Bad Fit). Check `data/applied_jobs.csv` and `data/rejected_jobs.csv` to confirm both exist and are non-empty.

---

## Further Reading

- [User Guide](USER_GUIDE.md) — Detailed walkthrough of each dashboard page, best practices, and skills management.
- [Developer Guide](DEVELOPER_GUIDE.md) — Architecture deep-dive: CSS system, state management, ML pipeline, caching strategy.

---

## Contributing

1. Fork the repository and create a feature branch (`git checkout -b feat/your-feature`).
2. Make your changes with tests where applicable (`pytest tests/`).
3. Open a pull request with a clear description of the change and its motivation.

Bug reports and feature requests are welcome via GitHub Issues.

---

## License

Released under the [MIT License](LICENSE). You are free to use, modify, and distribute it for personal and commercial purposes with attribution.

---

*Dream Hunt — Built with Streamlit, Selenium, SentenceTransformers, and scikit-learn.*
