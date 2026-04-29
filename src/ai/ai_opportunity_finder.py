"""
Job AI Model — Multi-Signal Job Scoring Engine
===================================================
- Multi-signal scoring: skill match, title relevance, description semantic, experience fit
- Semantic similarity via SentenceTransformer (cached singleton)
- Smooth experience-aware scoring with configurable tolerance
- RandomForest classifier trained on user feedback
- Upskill recommendations with normalized skill matching
- Model versioning with accuracy tracking
"""

import pandas as pd
import json
import os
import joblib
import numpy as np
import re
import hashlib
from datetime import datetime
from typing import List, Tuple, Dict, Optional
from sklearn.ensemble import RandomForestClassifier
from collections import Counter
from sentence_transformers import SentenceTransformer
from src.utils.logger import setup_logger

logger = setup_logger("AI_Model")

# ── Project root (src/ai/ai_opportunity_finder.py → src/ai → src → root) ─
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Cached singletons ─────────────────────────────────────────────
_encoder_instance: Optional[SentenceTransformer] = None
_pdf_cache: Optional[str] = None
_pdf_mtime_hash: Optional[str] = None


def _get_encoder() -> SentenceTransformer:
    """Lazy-load SentenceTransformer once per process."""
    global _encoder_instance
    if _encoder_instance is None:
        logger.info("Loading SentenceTransformer (all-MiniLM-L6-v2)...")
        _encoder_instance = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("SentenceTransformer loaded.")
    return _encoder_instance


def _get_pdf_cache() -> Tuple[str, str]:
    """Return cached PDF text + mtime hash. Re-extracts only if PDFs changed."""
    global _pdf_cache, _pdf_mtime_hash

    # Use absolute paths relative to project root so this works from any cwd
    _data_dir = os.path.join(_PROJECT_ROOT, 'data')
    data_pdfs = (
        [os.path.join(_data_dir, f) for f in os.listdir(_data_dir) if f.endswith('.pdf')]
        if os.path.exists(_data_dir) else []
    )
    root_pdfs = [os.path.join(_PROJECT_ROOT, f) for f in os.listdir(_PROJECT_ROOT) if f.endswith('.pdf')]
    pdf_files = sorted(list(set(data_pdfs + root_pdfs)))

    if not pdf_files:
        return "", ""

    # Build hash from mtimes
    mtimes = [str(os.path.getmtime(p)) for p in pdf_files]
    current_hash = hashlib.md5("|".join(mtimes).encode()).hexdigest()

    if _pdf_cache is not None and _pdf_mtime_hash == current_hash:
        return _pdf_cache, current_hash

    pdf_text = ""
    try:
        from pypdf import PdfReader
        for pdf_file in pdf_files:
            try:
                with open(pdf_file, 'rb') as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            pdf_text += text + " "
                logger.info(f"Extracted text from {pdf_file}")
            except Exception as e:
                logger.error(f"Error reading {pdf_file}: {e}")
    except ImportError:
        logger.warning("pypdf not installed. Cannot read PDF profiles.")

    _pdf_cache = pdf_text.lower()
    _pdf_mtime_hash = current_hash
    return _pdf_cache, current_hash


class JobAIModel:
    """Multi-signal job scoring model with caching and feedback learning."""

    # ── Signal weights ────────────────────────────────────────────
    W_SKILL = 0.35
    W_TITLE = 0.25
    W_DESC = 0.25
    W_EXP = 0.15

    def __init__(self, config_path: str = "config/profile_config.json",
                 model_path: str = "data/job_ai_model.pkl"):
        self.config_path = config_path
        self.model_path = model_path
        self.encoder = _get_encoder()

        # Load config
        self._config = self._load_config()
        self.min_experience = self._config.get("min_experience_years", 0)
        self.target_roles = self._config.get("target_roles", [])
        self.profile_skills = self._normalize_skills(self._config.get("profile_keywords", []))

        # Build focused profile texts for separate embeddings
        self.keywords = self._load_keywords()  # legacy combined text
        self._profile_summary = self._build_profile_summary()
        self._title_text = self._build_title_text()

        # Cache embeddings
        self._profile_summary_emb = None
        self._title_emb = None

        # Load ML model
        self.model, self.model_meta = self._load_model()

    # ── Config / Profile Loading ──────────────────────────────────

    def _load_config(self) -> dict:
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
        return {}

    def _normalize_skills(self, skills: List[str]) -> List[str]:
        """Normalize skill list: lowercase, strip, deduplicate, filter short."""
        seen = set()
        normalized = []
        for s in skills:
            s = s.strip().lower()
            if len(s) >= 2 and s not in seen:
                seen.add(s)
                normalized.append(s)
        return normalized

    def _build_profile_summary(self) -> str:
        """Build a focused profile summary for description matching.
        Uses the first ~300 words of resume PDF (not keyword soup)."""
        pdf_text, _ = _get_pdf_cache()
        if pdf_text:
            words = pdf_text.split()[:300]
            return " ".join(words)
        # Fallback: use top skills as summary
        return " ".join(self.profile_skills[:20])

    def _build_title_text(self) -> str:
        """Build a title matching text from target_roles."""
        if self.target_roles:
            return " ".join(r.lower() for r in self.target_roles)
        # Fallback: extract role-like keywords
        role_keywords = [s for s in self.profile_skills
                         if any(kw in s for kw in ['analyst', 'engineer', 'developer', 'lead', 'manager', 'architect'])]
        return " ".join(role_keywords) if role_keywords else " ".join(self.profile_skills[:10])

    def _load_keywords(self) -> str:
        """Legacy: combined text for backward compatibility."""
        combined_text = ""
        keywords = self._config.get("profile_keywords", [])
        roles = self._config.get("target_roles", [])
        combined_text += " ".join(set(k.lower() for k in keywords + roles if k)) + " "
        pdf_text, _ = _get_pdf_cache()
        if pdf_text:
            combined_text += pdf_text
        return combined_text.strip()

    def _load_model(self) -> Tuple[Optional[RandomForestClassifier], Dict]:
        if os.path.exists(self.model_path):
            try:
                payload = joblib.load(self.model_path)
                if isinstance(payload, dict) and "model" in payload:
                    return payload["model"], payload.get("meta", {})
                # Legacy: raw model pickle
                return payload, {}
            except Exception as e:
                logger.error(f"Failed to load existing model: {e}")
        return None, {}

    # ── Embedding Helpers (cached) ────────────────────────────────

    def _get_profile_summary_emb(self):
        if self._profile_summary_emb is None:
            self._profile_summary_emb = self.encoder.encode([self._profile_summary], show_progress_bar=False)
        return self._profile_summary_emb

    def _get_title_emb(self):
        if self._title_emb is None:
            self._title_emb = self.encoder.encode([self._title_text], show_progress_bar=False)
        return self._title_emb

    # ── Text / Experience Helpers ─────────────────────────────────

    @staticmethod
    def _get_field(row, key: str):
        """Safely get a field from a row (Series or dict), trying both cases."""
        if isinstance(row, pd.Series):
            return str(row.get(key, row.get(key.lower(), '')))
        return str(row.get(key, row.get(key.lower(), '')))

    def _prepare_text(self, row) -> str:
        """Safely combine job fields into a single text string."""
        title = self._get_field(row, 'Title')
        desc = self._get_field(row, 'Description')
        skills = self._get_field(row, 'Skills')
        return f"{title} {desc} {skills}".lower()

    @staticmethod
    def parse_experience(exp_str) -> List[int]:
        if not exp_str or exp_str in ("Not mentioned", "N/A", "nan", ""):
            return [0, 99]
        nums = re.findall(r'\d+', str(exp_str))
        if len(nums) >= 2:
            return [int(nums[0]), int(nums[1])]
        elif len(nums) == 1:
            n = int(nums[0])
            return [n, n + 5]
        return [0, 99]

    # ── Multi-Signal Scoring ──────────────────────────────────────

    def _skill_match_score(self, row) -> float:
        """Score 0-100: what % of the job's required skills match the user's profile."""
        job_skills_raw = self._get_field(row, 'Skills')
        job_desc = self._get_field(row, 'Description').lower()

        if not job_skills_raw or job_skills_raw in ('N/A', 'nan'):
            # Fall back to description keyword matching
            if not job_desc:
                return 50.0  # neutral
            matched = sum(1 for s in self.profile_skills if s in job_desc)
            return min(100, (matched / max(len(self.profile_skills[:15]), 1)) * 100)

        job_skills = [s.strip().lower() for s in job_skills_raw.split(',') if s.strip()]
        if not job_skills:
            return 50.0

        matched = 0
        for js in job_skills:
            for ps in self.profile_skills:
                # Fuzzy substring match (both directions)
                if ps in js or js in ps:
                    matched += 1
                    break

        return min(100, (matched / len(job_skills)) * 100)

    def _title_relevance_score(self, row) -> float:
        """Score 0-100: how relevant is the job title to target roles."""
        title = self._get_field(row, 'Title').lower()
        if not title:
            return 50.0

        title_emb = self.encoder.encode([title], show_progress_bar=False)
        profile_title_emb = self._get_title_emb()
        sim = float(np.dot(title_emb, profile_title_emb.T).flatten()[0])
        return max(0, min(100, sim * 100))

    def _description_semantic_score(self, row) -> float:
        """Score 0-100: semantic similarity of job description to focused profile."""
        desc = self._get_field(row, 'Description')
        if not desc or desc in ('N/A', 'nan'):
            return 50.0

        desc_emb = self.encoder.encode([desc.lower()[:1000]], show_progress_bar=False)
        profile_emb = self._get_profile_summary_emb()
        sim = float(np.dot(desc_emb, profile_emb.T).flatten()[0])
        return max(0, min(100, sim * 100))

    def _experience_fit_score(self, row) -> float:
        """Score 0-100: smooth gradient experience fit (not binary penalty)."""
        job_min, job_max = self.parse_experience(self._get_field(row, 'Experience'))
        user_exp = self.min_experience

        # If job has no experience requirement, neutral
        if job_min == 0 and job_max == 99:
            return 85.0

        # Perfect fit: user falls within range
        if job_min <= user_exp <= job_max:
            return 100.0

        # Close fit: within 1 year of range
        if job_min - 1 <= user_exp <= job_max + 1:
            return 85.0

        # Calculate distance-based penalty
        if user_exp < job_min:
            gap = job_min - user_exp
        else:
            gap = user_exp - job_max

        # Smooth decay: each year of gap = -12 points from 80
        score = max(10, 80 - (gap * 12))
        return float(score)

    # ── Batch Scoring (optimized) ─────────────────────────────────

    def _batch_multi_signal_scores(self, df: pd.DataFrame) -> List[Dict[str, float]]:
        """Batch compute multi-signal scores with embedding optimization."""
        if df.empty:
            return []

        # Batch encode all titles and descriptions at once
        titles = [str(row.get('Title', '')).lower() for _, row in df.iterrows()]
        descs = [str(row.get('Description', '')).lower()[:1000] for _, row in df.iterrows()]

        title_embs = self.encoder.encode(titles, show_progress_bar=False)
        desc_embs = self.encoder.encode(descs, show_progress_bar=False)

        profile_title_emb = self._get_title_emb()
        profile_desc_emb = self._get_profile_summary_emb()

        title_sims = np.dot(title_embs, profile_title_emb.T).flatten()
        desc_sims = np.dot(desc_embs, profile_desc_emb.T).flatten()

        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            skill = self._skill_match_score(row)
            title_score = max(0, min(100, float(title_sims[i]) * 100))
            desc_score = max(0, min(100, float(desc_sims[i]) * 100))
            exp = self._experience_fit_score(row)

            final = (skill * self.W_SKILL +
                     title_score * self.W_TITLE +
                     desc_score * self.W_DESC +
                     exp * self.W_EXP)

            results.append({
                "skill_match": round(skill, 1),
                "title_relevance": round(title_score, 1),
                "description_semantic": round(desc_score, 1),
                "experience_fit": round(exp, 1),
                "final": int(max(0, min(100, final))),
            })

        return results

    # ── Baseline Scoring (legacy, uses multi-signal now) ──────────

    def calculate_baseline_score(self, df: pd.DataFrame) -> List[int]:
        if not self.profile_skills or df.empty:
            logger.warning("No profile skills or empty dataframe. Returning 0 scores.")
            return [0] * len(df)

        try:
            breakdowns = self._batch_multi_signal_scores(df)
            return [b["final"] for b in breakdowns]
        except Exception as e:
            logger.error(f"Error in multi-signal scoring: {e}")
            return [0] * len(df)

    # ── ML Training ───────────────────────────────────────────────

    def _deduplicate_feedback(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate feedback entries by Job URL."""
        if "Job URL" not in df.columns:
            logger.warning("'Job URL' column missing from feedback data; skipping deduplication.")
            return df
        before = len(df)
        df = df.drop_duplicates(subset=["Job URL"], keep="last").reset_index(drop=True)
        if before > len(df):
            logger.info(f"Removed {before - len(df)} duplicate feedback entries.")
        return df

    def train(self, applied_csv: str = "data/applied_jobs.csv",
              rejected_csv: str = "data/rejected_jobs.csv") -> Tuple[bool, str]:
        df_list = []
        for path, label in [(applied_csv, 1), (rejected_csv, 0)]:
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path)
                    if not df.empty:
                        df = self._deduplicate_feedback(df)
                        df['label'] = label
                        df_list.append(df)
                except Exception as e:
                    logger.error(f"Error reading {path}: {e}")

        if not df_list:
            return False, "No feedback data available yet. Please rate some jobs first."

        df_train = pd.concat(df_list, ignore_index=True)
        df_train = self._deduplicate_feedback(df_train)

        if len(df_train['label'].unique()) < 2:
            return False, "Need both approved (👍) and rejected (👎) jobs to train the AI."

        texts = [self._prepare_text(row) for _, row in df_train.iterrows()]
        y = df_train['label'].values

        try:
            X_text = self.encoder.encode(texts, show_progress_bar=False)
            X_exp = np.array([self.parse_experience(row.get('Experience', ''))
                              for _, row in df_train.iterrows()])

            # Add multi-signal features
            signal_features = []
            for _, row in df_train.iterrows():
                skill = self._skill_match_score(row)
                exp_fit = self._experience_fit_score(row)
                signal_features.append([skill, exp_fit])
            X_signals = np.array(signal_features)

            X_final = np.hstack((X_text, X_exp, X_signals))

            # Train with class balancing
            clf = RandomForestClassifier(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=2,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1
            )
            clf.fit(X_final, y)

            # Simple validation: shuffle then holdout last 20%
            acc_msg = ""
            if len(y) >= 10:
                rng = np.random.default_rng(42)
                shuffle_idx = rng.permutation(len(y))
                X_shuf, y_shuf = X_final[shuffle_idx], y[shuffle_idx]
                split = int(len(y_shuf) * 0.8)
                clf_val = RandomForestClassifier(
                    n_estimators=200, max_depth=12, min_samples_leaf=2,
                    class_weight="balanced", random_state=42, n_jobs=-1
                )
                clf_val.fit(X_shuf[:split], y_shuf[:split])
                val_acc = clf_val.score(X_shuf[split:], y_shuf[split:])
                acc_msg = f" Validation accuracy: {val_acc:.1%}."

            meta = {
                "trained_at": datetime.now().isoformat(),
                "samples": len(y),
                "features": X_final.shape[1],
                "accuracy_note": acc_msg.strip(),
            }
            joblib.dump({"model": clf, "meta": meta}, self.model_path)
            self.model = clf
            self.model_meta = meta
            logger.info(f"Model trained on {len(y)} samples.{acc_msg}")
            return True, f"AI Model trained on {len(y)} feedback samples!{acc_msg}"
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return False, f"Training failed: {e}"

    # ── Prediction ────────────────────────────────────────────────

    def predict_scores(self, df: pd.DataFrame) -> List[int]:
        if df.empty:
            return []

        if self.model:
            try:
                texts = [self._prepare_text(row) for _, row in df.iterrows()]
                X_text = self.encoder.encode(texts, show_progress_bar=False)
                X_exp = np.array([self.parse_experience(row.get('Experience', ''))
                                  for _, row in df.iterrows()])
                signal_features = []
                for _, row in df.iterrows():
                    skill = self._skill_match_score(row)
                    exp_fit = self._experience_fit_score(row)
                    signal_features.append([skill, exp_fit])
                X_signals = np.array(signal_features)
                X_final = np.hstack((X_text, X_exp, X_signals))

                probabilities = self.model.predict_proba(X_final)[:, 1]
                logger.info("Scores predicted using ML model.")

                # Blend ML probability with multi-signal baseline
                baseline = self._batch_multi_signal_scores(df)
                scores = []
                for i in range(len(df)):
                    ml_score = int(probabilities[i] * 100)
                    base_score = baseline[i]["final"]
                    # 60% ML, 40% multi-signal baseline
                    blended = int(ml_score * 0.6 + base_score * 0.4)
                    scores.append(max(0, min(100, blended)))
                return scores
            except Exception as e:
                logger.error(f"Error predicting with ML model: {e}. Falling back to baseline.")

        logger.info("Scores predicted using multi-signal baseline.")
        return self.calculate_baseline_score(df)

    def predict_with_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return dataframe with score + breakdown columns for UI explainability."""
        if df.empty:
            return df

        breakdowns = self._batch_multi_signal_scores(df)
        scores = [b["final"] for b in breakdowns]

        # If ML model exists, blend
        if self.model:
            try:
                ml_scores = self.predict_scores(df)
                scores = ml_scores  # predict_scores already blends
            except Exception:
                pass

        df = df.copy()
        df['AI_Score'] = scores
        df['Score_Skill'] = [b['skill_match'] for b in breakdowns]
        df['Score_Title'] = [b['title_relevance'] for b in breakdowns]
        df['Score_Desc'] = [b['description_semantic'] for b in breakdowns]
        df['Score_Exp'] = [b['experience_fit'] for b in breakdowns]
        # Keep legacy columns for backward compat
        df['Score_Semantic'] = [b['description_semantic'] for b in breakdowns]
        df['Score_ExpPenalty'] = [int(100 - b['experience_fit']) for b in breakdowns]
        return df

    # ── Upskill Recommendations ───────────────────────────────────

    def get_upskill_recommendations(self, df: pd.DataFrame, top_n: int = 5) -> List[Tuple[str, int]]:
        if 'Skills' not in df.columns or df.empty:
            return []

        market_skills = Counter()
        for skills_str in df['Skills'].dropna():
            for s in str(skills_str).split(','):
                s = s.strip().lower()
                if len(s) >= 2:
                    market_skills[s] += 1

        known = set(self.profile_skills)

        recommendations = []
        for skill, count in market_skills.most_common():
            # Skip if skill is known (exact or substring match)
            if skill in known:
                continue
            if any(skill in k or k in skill for k in known):
                continue
            recommendations.append((skill.title(), count))
            if len(recommendations) >= top_n:
                break

        return recommendations

    def get_skill_coverage(self, df: pd.DataFrame) -> Dict:
        """Analyze how well user's skills cover the market."""
        if 'Skills' not in df.columns or df.empty:
            return {"coverage": 0, "total_unique": 0, "matched": 0, "missing": []}

        market_skills = Counter()
        for skills_str in df['Skills'].dropna():
            for s in str(skills_str).split(','):
                s = s.strip().lower()
                if len(s) >= 2:
                    market_skills[s] += 1

        known = set(self.profile_skills)

        matched = set()
        missing = []
        for skill, count in market_skills.most_common():
            is_known = skill in known or any(skill in k or k in skill for k in known)
            if is_known:
                matched.add(skill)
            else:
                missing.append((skill.title(), count))

        total = len(market_skills)
        coverage = (len(matched) / total * 100) if total > 0 else 0
        return {
            "coverage": round(coverage, 1),
            "total_unique": total,
            "matched": len(matched),
            "missing": missing[:10],
        }

    def get_model_info(self) -> Dict:
        """Return model metadata for UI display."""
        info = {
            "loaded": self.model is not None,
            "keywords_length": len(self.keywords),
            "experience_years": self.min_experience,
            "scoring_mode": "Multi-Signal (4 components)" if not self.model else "ML + Multi-Signal Blend",
        }
        if self.model_meta:
            info.update(self.model_meta)
        return info
