# Makefile for Literature Review Pipeline

# Default values
QUERY ?= "cognitive behavioral therapy AND depression"
YEAR_FROM ?= 2015
YEAR_TO ?= 2025
LANGS ?= en,fr
TOP_N ?= 2000
ALLOW_PREPRINTS ?= false
PROJECT_NAME ?= "My Literature Review"
ZOTERO_COLLECTION ?= "Literature Review Collection"

# Help
.PHONY: help
help:
	@echo "Literature Review Pipeline Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install dependencies with Poetry"
	@echo "  setup            Setup project (install + pre-commit)"
	@echo ""
	@echo "Main workflow:"
	@echo "  run              Run complete pipeline (harvest + process + report)"
	@echo "  harvest          Harvest papers from APIs"
	@echo "  process          Process harvested data"
	@echo "  screen           Launch Streamlit screening app"
	@echo "  zotero           Push screened papers to Zotero"
	@echo "  report           Generate PRISMA report"
	@echo ""
	@echo "Development:"
	@echo "  test             Run pytest tests"
	@echo "  lint             Run linting tools"
	@echo "  format           Format code with black and isort"
	@echo "  clean            Clean temporary files"
	@echo ""
	@echo "Variables:"
	@echo "  QUERY='your query'        Search query"
	@echo "  YEAR_FROM=2015            Start year"
	@echo "  YEAR_TO=2025              End year"
	@echo "  LANGS=en,fr               Allowed languages"
	@echo "  TOP_N=2000                Max papers per source"
	@echo "  ALLOW_PREPRINTS=false     Include preprints"
	@echo "  ZOTERO_COLLECTION='name'  Zotero collection name"

# Setup
.PHONY: install setup
install:
	poetry install

setup: install
	poetry run pre-commit install

# Main pipeline
.PHONY: run harvest process screen zotero report
run:
	poetry run python -m src.cli harvest --query "$(QUERY)" --year-from $(YEAR_FROM) --year-to $(YEAR_TO) --langs $(LANGS) --top-n $(TOP_N)
	poetry run python -m src.cli process --allow-preprints $(ALLOW_PREPRINTS)
	poetry run python -m src.cli report

harvest:
	poetry run python -m src.cli harvest --query "$(QUERY)" --year-from $(YEAR_FROM) --year-to $(YEAR_TO) --langs $(LANGS) --top-n $(TOP_N)

process:
	poetry run python -m src.cli process --allow-preprints $(ALLOW_PREPRINTS)

screen:
	poetry run streamlit run app/streamlit_app.py

zotero:
	poetry run python -m src.cli zotero-push --collection "$(ZOTERO_COLLECTION)"

report:
	poetry run python -m src.cli report

# Development
.PHONY: test lint format clean
test:
	poetry run pytest

lint:
	poetry run ruff check src tests app
	poetry run black --check src tests app
	poetry run isort --check-only src tests app

format:
	poetry run black src tests app
	poetry run isort src tests app
	poetry run ruff check --fix src tests app

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

# R alternative (optional)
.PHONY: r-dedup
r-dedup:
	Rscript r/dedup.R
