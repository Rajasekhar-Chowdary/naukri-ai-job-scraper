# User Guide: Dream Hunt Dashboard

Welcome to the Dream Hunt application. This guide will help you understand how to configure your profile, run the scraper, and interact with the AI-powered dashboard.

## 1. Initial Setup

Before using the app, you need to provide it with your context.

1. **Add Your Resume**: Place your current resume (PDF format) directly into the `data/` folder. The AI reads this file to extract your professional background and generate a semantic summary for matching.
2. **Configure Your Profile**: The application uses `config/profile_config.json`. The dashboard allows you to manage most of this via the UI, but it includes:
   - `target_roles`: A list of job titles you are looking for (e.g., "Senior Data Analyst", "Analytics Engineer").
   - `min_experience_years`: Your current years of experience.
   - `profile_keywords`: A list of your specific technical skills.

## 2. Page Navigation

### 🕸️ Scraper Page
This page is your control center for fetching new jobs.
- **Search Parameters**: Set your target role, location, experience level, and how far back you want to search (e.g., "Last 24 hours").
- **Max Jobs**: Limit how many jobs the scraper attempts to pull.
- **Run the Scraper**: Click the large button to start. The scraper will launch an automated browser (running silently in the background if 'Headless' is checked) and navigate Naukri.com. Progress is shown in real-time.

### 🧠 AI Scoring Page
Once jobs are scraped, this is where you spend most of your time. The AI automatically scores every scraped job against your profile.

- **Job Feed**: The main column shows the jobs, sorted by their AI Score. 
- **Score Breakdown**: Click the `▼ Match Intelligence` toggle on any job card to see exactly *why* a job got its score. The score is broken down into four parts:
  - Skill Match (Exact skill hits)
  - Title Relevance (Does the role match your targets?)
  - Description Match (Semantic alignment with your resume)
  - Experience Fit (Are you in the required experience range?)
- **Training the AI**: Under each job, you will see a `👍 Good Fit` and `👎 Bad Fit` button. **Use these!** Clicking them moves the job to your feedback database, which the Random Forest ML model uses to get smarter and adapt to your personal preferences over time.
- **Skills Management**: At the bottom of the page, you can dynamically add or remove skills from your profile. The AI will instantly recalculate scores based on your new skill set.

### 📊 Dashboard Page
This is your market intelligence center.
- **Stats Strip**: A quick glance at how many jobs are top matches (>85) vs good matches (>50).
- **Your Profile vs The Market**: A crucial tool for upskilling. It analyzes the skills requested in all scraped jobs and compares them to your configured skills. It will explicitly list your "Top Missing Skills"—these are the technologies you should consider learning next to increase your marketability.
- **Hiring Trends**: Shows which companies are currently hiring the most for your role, and in which cities.
- **Model Status**: Check the "AI Feedback Summary" to see if your ML model is fully trained or if it needs more feedback data.

## 3. Best Practices
- **Scrape Frequently**: Job boards move fast. Run the scraper daily using the "Last 24 hours" filter to keep your feed fresh.
- **Provide Feedback**: The baseline AI is powerful, but the ML model makes it personalized. Try to rate at least 20-30 jobs to give the ML model enough data to activate.
- **Keep Skills Updated**: If you learn a new tool (e.g., dbt, Snowflake), add it immediately via the Skills Management section on the AI Scoring page to instantly boost your scores for relevant jobs.
