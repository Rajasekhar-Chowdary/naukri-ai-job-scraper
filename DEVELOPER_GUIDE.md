# Developer Guide: Architecture & Systems

This guide explains the underlying architecture of the Dream Hunt dashboard.

## 1. Core Architecture

The system is split into two primary decoupled components:
- **Scraping Engine (`src/scraper/`)**: Built with `selenium` and `undetected_chromedriver`. It handles the messy reality of web scraping (bypassing bot detection, handling dynamic pagination, extracting structured data).
- **Intelligence Dashboard (`src/dashboard/` & `src/ai/`)**: A Streamlit application backed by a dual-layer AI scoring system (`SentenceTransformers` + `scikit-learn`).

Communication between the two happens entirely via the file system (`data/` CSV files). This decoupled nature ensures that scraper crashes do not affect the UI, and the UI can rapidly load data without waiting for the web.

## 2. Multi-Signal AI Scoring System (`JobAIModel`)

The core of the intelligence layer is located in `src/ai/ai_opportunity_finder.py`. 

### The Baseline System (Multi-Signal)
Rather than relying on a single text embedding, the baseline model calculates a deterministic score using 4 weighted signals:
1. **Skill Match Score (35%)**: Tokenizes both the user's `profile_keywords` and the job's `Skills` field. Calculates an exact and substring match percentage.
2. **Title Relevance (25%)**: Uses `all-MiniLM-L6-v2` (`SentenceTransformer`) to calculate the cosine similarity between the job's `Title` and a concatenated string of the user's `target_roles`.
3. **Description Semantic (25%)**: Uses `SentenceTransformer` to calculate cosine similarity between the job's `Description` and a focused 300-word summary extracted from the user's `data/*.pdf` resume.
4. **Experience Fit (15%)**: A deterministic mathematical decay function. If the user's experience falls within the job's min/max range, they get 100%. For every year outside the range, a smooth linear penalty is applied.

### The Machine Learning Layer
When the user rates jobs, data is saved to `applied_jobs.csv` (Label 1) and `rejected_jobs.csv` (Label 0).
- The `train()` method vectorizes the text features and concatenates them with the numerical signals (experience, skill match).
- A `RandomForestClassifier` is trained on this matrix.
- If the model is successfully trained, the `predict_scores()` method blends the ML probability output with the deterministic Multi-Signal baseline (60% ML / 40% Baseline) to produce the final score.

## 3. UI Framework & "Ethereal Glass" Design System

Streamlit's default UI is notoriously generic. To counteract this, the project uses a custom, highly opinionated CSS framework defined in `src/dashboard/design.py`.

### Principles
- **DOM Injection**: CSS is injected via `st.markdown('<style>...</style>', unsafe_allow_html=True)`.
- **Glassmorphism**: Elements use `background: rgba(255, 255, 255, 0.02)` and `backdrop-filter: blur(20px)` to create a premium, translucent aesthetic.
- **Custom Components**: `design.py` exposes Python functions (like `compact_job_card`, `score_badge`, `section_header`) that return raw HTML strings. These are rendered in the dashboard pages using `st.markdown(..., unsafe_allow_html=True)`.

### Important Caveat regarding Streamlit Layout
You **cannot** wrap native Streamlit widgets (like `st.button` or `st.text_input`) inside custom HTML `div` tags rendered via `st.markdown`. Streamlit will auto-close the HTML tags, resulting in broken layouts. Custom HTML structures must be completely self-contained, or they must rely on Streamlit's native `st.container()` and column structures for layout.

## 4. State Management & Caching

- `@st.cache_resource` is used to load the `JobAIModel` (and its heavy `SentenceTransformer` model) exactly once into memory.
- **Cache Invalidation**: Because `JobAIModel` might be updated, we check for expected attributes (like `hasattr(ai_model, "profile_skills")`). If an attribute is missing, we programmatically clear the cache (`st.cache_resource.clear()`) to force a reload of the Python class.
- `@st.cache_data(ttl=60)` is used to load the latest CSV from the `data/` folder, ensuring the UI remains snappy but refreshes automatically a minute after a new scrape completes.
