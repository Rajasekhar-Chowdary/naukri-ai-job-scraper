# Developer Guide — Architecture & Systems

This guide covers the internal architecture of Dream Hunt: how the components fit together, design decisions, extension points, and gotchas.

---

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Data Flow](#data-flow)
- [Scraping Engine](#scraping-engine)
- [AI Scoring System](#ai-scoring-system)
- [UI Framework — "Ethereal Glass"](#ui-framework--ethereal-glass)
- [State Management & Caching](#state-management--caching)
- [Session Status Protocol](#session-status-protocol)
- [Logging](#logging)
- [Testing](#testing)
- [Extension Points](#extension-points)
- [Known Limitations](#known-limitations)

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Streamlit UI                         │
│  app.py  │  1_Scraper.py  │  2_AI_Scoring.py  │  3_Dashboard.py │
└──────────────────┬──────────────────────────────────────┘
                   │ reads/writes
         ┌─────────▼──────────┐
         │    data/ (CSVs)    │   ◄── single source of truth
         └─────────┬──────────┘
                   │ reads
┌──────────────────▼──────────┐   ┌────────────────────────┐
│   src/ai/ai_opportunity_    │   │  src/scraper/          │
│   finder.py (JobAIModel)    │   │  scraper_cli.py        │
│   SentenceTransformer +     │   │  (NaukriScraper)       │
│   RandomForest              │   │  Selenium + WebDriver  │
└─────────────────────────────┘   └────────────────────────┘
```

The scraper and the UI are **fully decoupled** — they communicate only through CSV files in `data/`. A scraper crash does not affect the dashboard, and the dashboard can load historical data without the scraper running.

---

## Data Flow

### Scrape → Score → Display

```
NaukriScraper.scrape()
  → _scrape_page() extracts job dicts
  → pd.DataFrame(all_jobs)
  → drop_duplicates (in-run)
  → cross-scrape dedup (historical URL check)
  → JobAIModel.predict_scores(df)   ← scores injected into df
  → df.to_csv("data/naukri_*.csv")
  → high-score jobs appended to "data/top_matches.csv"

Streamlit page loads
  → get_latest_data() reads most-recently-modified naukri_*.csv
  → ai_model.predict_with_breakdown(df)  ← adds Score_* columns
  → renders job cards
```

### Feedback → Training → Blended Scoring

```
User clicks 👍/👎
  → save_feedback() appends row to applied_jobs.csv / rejected_jobs.csv

User clicks Retrain
  → JobAIModel.train()
    → reads applied_jobs.csv (label=1) + rejected_jobs.csv (label=0)
    → _deduplicate_feedback()
    → encode texts with SentenceTransformer
    → concatenate [text_emb | experience | skill_score | exp_fit_score]
    → RandomForestClassifier.fit(X, y)
    → saves to data/job_ai_model.pkl

Next predict_scores() call
  → loads pkl, gets ML probability
  → blends: 0.6 * ml_prob + 0.4 * baseline
```

---

## Scraping Engine

**File:** `src/scraper/scraper_cli.py`

### URL Construction

`build_naukri_url()` assembles Naukri search URLs. The URL format is:

```
https://www.naukri.com/{role}-jobs{-in-location}{-pagenum}?k={role}&l={location}&jobAge={days}&...
```

Query parameters are built conditionally — only filters that have non-default values are appended. This matches what a human user would generate manually via Naukri's search filters.

### Selector Strategy

The scraper uses multiple CSS selector fallbacks per field (defined as class-level constants `_CARD_SELECTORS`, `_TITLE_SELECTORS`, etc.). The `_find_text()` static method tries each selector in order and returns the first non-empty match. This makes the scraper resilient to minor Naukri DOM changes.

### Retry Logic

Page fetches retry up to `_MAX_PAGE_RETRIES` (2) times with a random wait of 4–8 seconds between attempts. On persistent failure, the page is skipped and the scraper continues with the remaining pages rather than aborting the entire run.

### Cross-run Deduplication

After each scrape, the new `Job URL` column is checked against all previously saved `naukri_*.csv` files in `data/`. Matching URLs are dropped before saving. This prevents the same listing from accumulating across daily scrapes.

### Session Status File

During a scrape, `_write_session_status()` writes a JSON snapshot to `data/.scrape_session.json` at each pipeline stage. The Streamlit Scraper page polls this file to render a live progress pipeline without needing a persistent background thread or a WebSocket connection.

---

## AI Scoring System

**File:** `src/ai/ai_opportunity_finder.py`

### Singleton Management

Two module-level singletons prevent redundant model loading across Streamlit reruns:

- `_encoder_instance` — the `SentenceTransformer` model (loaded once per Python process)
- `_pdf_cache` / `_pdf_mtime_hash` — the extracted resume text, invalidated only when the PDF's modification time changes

### Signal Computation

#### Skill Match (`W_SKILL = 0.35`)

Tokenises the job's `Skills` field on commas, then checks each job skill against every profile skill using bidirectional substring matching (`ps in js or js in ps`). Returns the percentage of job skills matched. Falls back to description keyword scan if `Skills` is `N/A`.

#### Title Relevance (`W_TITLE = 0.25`)

Encodes the job title and the concatenated `target_roles` string with `all-MiniLM-L6-v2`. Returns cosine similarity × 100. Profile title embedding is lazily computed and cached on the `JobAIModel` instance.

#### Description Semantic (`W_DESC = 0.25`)

Encodes the first 1000 characters of the job description and the first 300 words of the resume PDF. Returns cosine similarity × 100. Both embeddings are cached on the instance after first computation.

#### Experience Fit (`W_EXP = 0.15`)

```python
if within range:         return 100.0
if within 1 year:        return 85.0
else:                    return max(10, 80 - gap_years * 12)
```

This smooth decay avoids binary pass/fail behaviour and preserves borderline candidates in the feed.

### Batch Encoding

`_batch_multi_signal_scores()` encodes all titles and descriptions in a single `encoder.encode()` call, then uses vectorised dot products for cosine similarity. This reduces encoding time from O(n) single calls to two batch calls regardless of dataset size.

### ML Feature Matrix

The training and prediction feature matrix is constructed as:

```
X = [ sentence_embeddings (384) | experience_range (2) | skill_score (1) | exp_fit_score (1) ]
    shape: (n_samples, 388)
```

The `RandomForestClassifier` outputs class probabilities; `predict_proba()[:, 1]` is the "good fit" probability used for scoring.

### Model Versioning

The `.pkl` file stores a dict `{"model": clf, "meta": {...}}` where `meta` includes `trained_at`, `samples`, `features`, and a validation accuracy note. This metadata is surfaced in the Model Status widget in the UI.

---

## UI Framework — "Ethereal Glass"

**File:** `src/dashboard/design.py`

### Approach

Streamlit renders a React SPA. Custom styling is injected by calling `st.markdown('<style>...</style>', unsafe_allow_html=True)` once per page load via `inject_css()`. All styles are defined in a single CSS string (`GLASS_CSS`) to avoid multiple injection calls and ordering issues.

### Design Tokens

CSS custom properties defined on `:root`:

| Variable | Purpose |
|---|---|
| `--glass-bg` | Card background (semi-transparent dark) |
| `--glass-bd` | Card border (subtle white at 8% opacity) |
| `--t1`, `--t2`, `--t3` | Text hierarchy (primary, secondary, muted) |
| `--td` | Description text colour |
| `--track` | Progress bar background |
| `--div` | Divider colour |

### Component Functions

`design.py` exposes Python functions that return raw HTML strings rendered via `st.markdown(..., unsafe_allow_html=True)`:

| Function | Returns |
|---|---|
| `score_badge(score, size)` | Coloured circular badge |
| `score_breakdown_bar(semantic, penalty, final)` | Horizontal score bar with label |
| `skill_coverage_ring(coverage, matched, total)` | Donut ring with percentage label |
| `model_status_card(is_trained, samples, accuracy, trained_at)` | Model metadata card |
| `filter_chip(label, active)` | Small pill tag for active filters |
| `section_header(title, subtitle, eyebrow)` | Page section heading block |
| `page_header(title, subtitle, eyebrow)` | Full-width page title block |
| `top_nav(current_page)` | Horizontal navigation bar |
| `welcome_card(step, title, body)` | "How it works" step card |
| `_flat(html)` | Collapses multiline HTML to a single line (prevents Streamlit markdown issues) |

### Critical Constraint

**You cannot nest native Streamlit widgets inside custom HTML rendered via `st.markdown`.** Streamlit auto-closes HTML tags when it encounters widget calls, breaking layouts. Custom HTML blocks must be entirely self-contained. Use `st.columns()` and `st.container()` for structural layout, then inject HTML styling within those containers.

---

## State Management & Caching

### `@st.cache_resource`

Used for `JobAIModel` — loads the SentenceTransformer and trained RandomForest once into memory and reuses across reruns. Cache is cleared explicitly after retraining via `st.cache_resource.clear()`.

A defensive check guards against API changes across deployments:

```python
ai_model = get_ai_model()
if not hasattr(ai_model, "profile_skills"):
    st.cache_resource.clear()
    ai_model = get_ai_model()
```

### `@st.cache_data(ttl=60)`

Used for CSV loading (`get_latest_data()`). The 60-second TTL ensures the UI picks up new scrape results automatically without requiring a manual page reload, while keeping the pandas read off the hot path for normal browsing.

### Session State

`st.session_state` persists the following across reruns within a session:

| Key | Purpose |
|---|---|
| `rated_jobs` | `{url: "applied" \| "rejected"}` — prevents double-rating in the UI |
| `ai_page_offset` | Current pagination position in the job feed |
| `ai_page_size` | Jobs per page (10 / 20 / 50 / 100) |
| `_last_filter_state` | Serialised filter hash — resets pagination when filters change |

---

## Session Status Protocol

During a scrape, `NaukriScraper._update_stage()` writes a JSON file to `data/.scrape_session.json`:

```json
{
  "stage": "Fetching",
  "stage_index": 1,
  "total_stages": 5,
  "percent": 35,
  "message": "Loading page 2 of 5...",
  "jobs_found": 20,
  "error": false,
  "done": false,
  "timestamp": "2026-04-30T14:22:11.123456",
  "result": null
}
```

The `progress_callback` in the Scraper page reads this via the Streamlit render loop to update the pipeline visualisation. The file is deleted by `clear_session_status()` before each scrape starts and can be safely absent (the UI handles the missing-file case).

---

## Logging

**File:** `src/utils/logger.py`

`setup_logger(name)` returns a logger that writes to both `logs/app.log` (rotating file handler) and stdout. Every module calls `setup_logger(__name__)` at module level. Logs are timestamped and include the logger name, enabling easy filtering by component (e.g. `grep "Scraper" logs/app.log`).

---

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

| File | Coverage |
|---|---|
| `tests/test_scraper.py` | URL builder, selector fallback logic, deduplication |
| `tests/test_ai_model.py` | Score computation, experience parsing, skill normalisation |

Tests do not require a live Naukri connection or a GPU. The SentenceTransformer is mocked in AI model tests to keep the suite fast.

To add a test for a new scraper selector, use the fixtures in `test_scraper.py` — they provide a minimal BeautifulSoup tree that mirrors the Naukri card structure.

---

## Extension Points

### Adding a new job board

1. Create `src/scraper/new_board_scraper.py` mirroring the `NaukriScraper` class interface (`scrape()` method, `_update_stage()` calls, same output column schema).
2. The `JobAIModel` is board-agnostic — pass any DataFrame with `Title`, `Company`, `Description`, `Skills`, `Experience` columns.
3. Add a new Scraper page or a board-selector toggle in `1_🕸️_Scraper.py`.

### Adding a new AI signal

In `ai_opportunity_finder.py`:

1. Implement `_your_signal_score(self, row) -> float` returning 0–100.
2. Add the weight as a class constant `W_YOUR_SIGNAL`.
3. Update `_batch_multi_signal_scores()` to include the new signal in the weighted sum.
4. Add a `Score_YourSignal` column in `predict_with_breakdown()`.
5. Update `score_breakdown_bar()` in `design.py` if you want it visualised in the job card.

### Persisting feedback to a database

Replace the CSV append logic in `save_feedback()` (`2_🧠_AI_Scoring.py`) with an insert into SQLite or PostgreSQL. The `JobAIModel.train()` method reads from file paths — update those arguments or override `_deduplicate_feedback()` to accept a DataFrame directly.

---

## Known Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| Naukri DOM changes | Scraper returns 0 jobs when selectors break | Update `_*_SELECTORS` constants in `scraper_cli.py` |
| CAPTCHA challenges | Scraper collects 0–few jobs | Run with `headless=False`; solve manually |
| PDF text extraction requires text-based PDFs | Scanned/image PDFs return no text | Export resume as a proper text PDF from Word/Google Docs |
| SentenceTransformer on first run | ~80 MB download, 10–30s delay | Pre-download and cache via `SENTENCE_TRANSFORMERS_HOME` |
| ML model requires both label classes | Retraining fails with only one class | Rate at least one job on each side before retraining |
| Dashboard always loads the latest CSV | Cannot compare across scrape sessions | Export CSVs manually before each new scrape if you need history |
