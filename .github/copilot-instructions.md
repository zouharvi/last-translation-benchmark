# Last Translation Benchmark

Python-based annotation platform for translation evaluation with web UI.

## Structure

- `server/` - Python backend (FastAPI)
  - `__init__.py` - FastAPI server
  - `__main__.py` - CLI entry point
  - `services.py` - Translation & LLM API logic
  - `utils.py` - Config parsing and helpers
  - `tests/` - Python tests
- `web/` - TypeScript/HTML frontend
  - Built with webpack to `server/static/`
- `data/` - JSON data store (`db.json`)

## Build & Test

**Setup:**
```bash
pip install -e .
cd web && npm install
```

**Lint (required before commit):**
```bash
ruff check server
ruff check --select=I server
```

**Test:**
```bash
pytest server/tests/
```

**Build web:**
```bash
cd web && npm run build
```

**Run locally:**
```bash
python3 server
```

## Requirements

- Python ≥3.12
- Node.js 18
- Always run `ruff check` and `ruff check --select=I server` before committing Python changes
- Web builds must succeed before committing frontend changes
- Tests in `server/tests/` must pass

## Style Guide

- Write minimal, elegant code—no unnecessary fluff
- Prioritize maintainability and readability
- Keep functions focused and concise
- Avoid over-engineering solutions

## Key Facts

- Backend in Python with FastAPI, frontend in TypeScript
- Configuration via `config.toml`
- CI runs ruff, pytest, and npm build on all PRs
