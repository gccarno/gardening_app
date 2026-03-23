# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python-based garden planning application. The project is in early development — the tech stack and framework have not yet been finalized.

## Language & Tooling

This is a **Python** project (inferred from `.gitignore`). Once dependencies and a framework are chosen, update this file with the specific setup commands.

Common Python development commands (adjust based on chosen package manager):

```bash
# Using uv (modern, fast)
uv sync                  # Install dependencies
uv run python main.py    # Run app
uv run pytest            # Run tests
uv run pytest tests/test_foo.py::test_bar  # Run a single test
uv run ruff check .      # Lint
uv run ruff format .     # Format

# Using pip + venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Architecture

To be documented as the project evolves. Update this file when the framework, data model, and directory structure are established.
