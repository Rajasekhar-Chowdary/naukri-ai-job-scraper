# Dream Hunt: AI-Powered Job Scraper & Dashboard

A production-ready job intelligence platform that automates scraping jobs from Naukri.com and uses an advanced Multi-Signal AI scoring system to rank opportunities against your specific resume and target roles.

## 🌟 Key Features

### 1. Automated Job Scraping
- Headless Selenium scraper specifically tuned for Naukri.com.
- Bypasses anti-bot mechanisms using stealth mode.
- Extracts Title, Company, Location, Experience, complete Description, and extracted Skills.

### 2. Multi-Signal AI Scoring System
The scoring system acts as an automated recruiter, analyzing your fit across four distinct signals:
- **Skill Match (35%)**: Exact and substring matching of required vs. owned skills.
- **Title Relevance (25%)**: Semantic similarity between the job title and your target roles.
- **Description Semantic (25%)**: Deep semantic analysis of the job description against a focused summary of your resume.
- **Experience Fit (15%)**: A smooth gradient algorithm that calculates how well your years of experience fit the required range.

### 3. Machine Learning Feedback Loop
- Rate jobs as 👍 "Good Fit" or 👎 "Bad Fit".
- The system trains a `RandomForestClassifier` on your feedback.
- Scores naturally blend between the multi-signal baseline and the ML predictions as you use the app.

### 4. "Ethereal Glass" UI Dashboard
A stunning, custom-built Streamlit interface featuring:
- **🕸️ Scraper Interface**: Launch headless scrapes directly from the UI.
- **🧠 AI Scoring**: View personalized job feeds, read deep explanations of *why* a job matched, and manage your skills on the fly.
- **📊 Intelligence Dashboard**: Get market analytics, skill coverage rings, top hiring companies, and a detailed "Profile vs Market" skill gap analysis.

---

## 🚀 Quickstart Guide

### 1. Installation
Clone the repository and install the dependencies:
```bash
git clone <your-repo>
cd naukri-job-scraper-dashboard-main
pip install -r requirements.txt
```

### 2. Configure Your Profile
Copy the example config and customize it with your skills and target roles:
```bash
cp config/profile_config.example.json config/profile_config.json
```
Edit `config/profile_config.json` to add your experience, skills, and target job titles.

### 3. Add Your Resume
Place your resume PDF into the `data/` folder. The AI uses this for deep semantic matching.

### 4. Run the Application
Launch the unified dashboard:
```bash
python run_dashboard.py
```
This will open the interface in your browser (usually at `http://localhost:8501`).

---

## 📂 Project Structure

```
├── config/
│   ├── profile_config.json          # Your skills, target roles, and scraper settings (gitignored)
│   └── profile_config.example.json  # Example template
├── data/
│   ├── Your_Resume.pdf              # Your resume for semantic matching (gitignored)
│   ├── applied_jobs.csv             # Feedback data (gitignored)
│   ├── rejected_jobs.csv            # Feedback data (gitignored)
│   └── naukri_jobs_*.csv            # Raw scraped outputs (gitignored)
├── src/
│   ├── ai/
│   │   └── ai_opportunity_finder.py # The ML and multi-signal scoring engine
│   ├── scraper/
│   │   └── scraper_cli.py           # Core Selenium scraping logic
│   ├── dashboard/
│   │   ├── app.py                   # Streamlit entry point
│   │   ├── design.py                # Custom 'Ethereal Glass' CSS framework
│   │   └── pages/                   # Individual dashboard pages
│   └── utils/
│       └── logger.py                # Centralized logging
├── run_dashboard.py                 # Main UI entry point
└── tests/                           # pytest suite
```

## 📖 Further Reading
- **[User Guide](USER_GUIDE.md)**: Detailed instructions on how to use the dashboard, configure skills, and train the AI.
- **[Developer Guide](DEVELOPER_GUIDE.md)**: Deep dive into the architecture, custom CSS components, and ML logic.