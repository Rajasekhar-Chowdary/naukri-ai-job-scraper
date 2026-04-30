# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-source scraper architecture (Naukri, LinkedIn, Indeed)
- SQLite database layer replacing CSV storage
- APScheduler background runner for 24/7 scraping
- Email, Discord, and Slack notifications for top matches
- Docker + docker-compose for easy deployment
- GitHub Actions CI/CD with lint, type check, security scan, and Docker build
- Pre-commit hooks for code quality
- Automated release workflow
- Database test suite

## [1.0.0] - 2026-04-30

### Added
- Initial release: Naukri.com scraper with Selenium
- Multi-signal AI scoring (skill, title, description, experience)
- RandomForest ML feedback loop
- Streamlit dashboard with Ethereal Glass UI
- Resume PDF semantic matching
- Skills management and upskill recommendations
