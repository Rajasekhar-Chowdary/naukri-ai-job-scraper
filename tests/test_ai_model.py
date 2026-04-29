"""
Tests for the production JobAIModel.
"""
import pytest
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.ai.ai_opportunity_finder import JobAIModel


class TestJobAIModel:
    def test_initialization(self):
        model = JobAIModel(config_path="nonexistent.json", model_path="nonexistent.pkl")
        assert isinstance(model.keywords, str)
        assert model.min_experience == 0
        assert model.model is None

    def test_parse_experience(self):
        assert JobAIModel.parse_experience("5-10 Yrs") == [5, 10]
        assert JobAIModel.parse_experience("3 Yrs") == [3, 8]
        assert JobAIModel.parse_experience("Not mentioned") == [0, 99]
        assert JobAIModel.parse_experience("") == [0, 99]
        assert JobAIModel.parse_experience("N/A") == [0, 99]

    def test_experience_fit_score(self):
        model = JobAIModel(config_path="nonexistent.json")
        model.min_experience = 5

        # Perfect fit: user falls within range
        row_fit = pd.Series({"Experience": "4-7 Yrs"})
        assert model._experience_fit_score(row_fit) == 100.0

        # Close fit: within 1 year of range
        row_close = pd.Series({"Experience": "3-4 Yrs"})
        assert model._experience_fit_score(row_close) == 85.0

        # Way too senior
        row_senior = pd.Series({"Experience": "10-15 Yrs"})
        assert model._experience_fit_score(row_senior) < 50.0

        # Too junior
        row_junior = pd.Series({"Experience": "0-2 Yrs"})
        assert model._experience_fit_score(row_junior) < 80.0

        # No experience requirement
        row_none = pd.Series({"Experience": "Not mentioned"})
        assert model._experience_fit_score(row_none) == 85.0

    def test_baseline_score(self):
        model = JobAIModel(config_path="nonexistent.json")
        model.profile_skills = ["python", "sql", "data", "analyst"]
        model.min_experience = 3

        df = pd.DataFrame({
            "Title": ["Python Developer", "HR Manager", "Data Analyst"],
            "Company": ["A", "B", "C"],
            "Location": ["X", "Y", "Z"],
            "Experience": ["2-4 Yrs", "5-10 Yrs", "3-5 Yrs"],
            "Description": ["Python coding", "People management", "SQL and analytics"],
            "Skills": ["Python, SQL", "Communication", "SQL, Python, Tableau"],
            "Job URL": ["#1", "#2", "#3"],
        })

        scores = model.calculate_baseline_score(df)
        assert len(scores) == 3
        # Python Dev and Data Analyst should score higher than HR Manager
        assert scores[0] > scores[1]
        assert scores[2] > scores[1]

    def test_predict_empty_df(self):
        model = JobAIModel(config_path="nonexistent.json")
        assert model.predict_scores(pd.DataFrame()) == []

    def test_skill_coverage(self):
        model = JobAIModel(config_path="nonexistent.json")
        model.profile_skills = ["python", "sql", "tableau"]

        df = pd.DataFrame({
            "Skills": ["Python, SQL, AWS", "Python, Tableau", "Java, Kubernetes"],
        })
        coverage = model.get_skill_coverage(df)
        assert 0 <= coverage["coverage"] <= 100
        assert coverage["total_unique"] > 0
        assert isinstance(coverage["missing"], list)

    def test_upskill_recommendations(self):
        model = JobAIModel(config_path="nonexistent.json")
        model.profile_skills = ["python", "sql"]

        df = pd.DataFrame({
            "Skills": ["Python, AWS, Docker", "SQL, AWS, Kubernetes", "Python, Machine Learning"],
        })
        recs = model.get_upskill_recommendations(df, top_n=3)
        assert isinstance(recs, list)
        # Should not recommend python or sql
        for skill, _ in recs:
            assert skill.lower() not in ("python", "sql")
