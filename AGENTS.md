# Repository Guidelines

## Project Structure & Module Organization
Service entry points live in `main.py`, `api.py`, and `api_v2.py`; core retrieval logic sits in `rag_pipeline.py`, `vector_store.py`, `llm_factory.py`, plus helpers like `data_loader.py` and `config.py`. Authentication work stays in `auth.py` and the `auth_standalone/` experiments—coordinate with `AUTH_SETUP.md` before touching them. Pre-processed corpora are tracked in `chunks/`, while generated Qdrant data lands in `qdrant_storage/` and should not be hand-edited. UI prototypes live in `frontend/` and `frontend_v2/`, and backend regression scripts (`test_*.py`) and their JSON reports remain at the repository root.

## Build, Test, and Development Commands
Activate the environment via `source venv/bin/activate`, then install dependencies with `pip install -r requirements.txt` when libraries change. Bring up Qdrant before API work using `docker-compose up -d` (and `docker-compose down` when finished). Start the service with `python main.py`; it answers on `http://localhost:8000`. After posting to `/initialize` with `recreate_collection=true`, run `python quick_test_retrieval.py` for smoke coverage and `python test_retrieval_accuracy.py` for the full suite.

## Coding Style & Naming Conventions
Use standard PEP 8 spacing: four-space indent, `snake_case` for functions and modules, `CamelCase` for classes, `UPPER_CASE` for configuration constants. Keep functions in `rag_pipeline.py` and `vector_store.py` small and composable, and add type hints when exposing new public helpers. Document non-obvious behaviour with concise docstrings or inline comments; no formatter is enforced, so maintain consistent import grouping manually.

## Testing Guidelines
Tests are plain Python scripts guarded by `if __name__ == "__main__":`, so execute them directly with `python test_*.py`. Record new scenarios near similar cases and update associated `*_test_report.json` artifacts when expectations change. Keep retrieval checks under two minutes and note any external dependencies (Ollama hosts, Qdrant ports) in the relevant README or script header comments.

## Commit & Pull Request Guidelines
Commits in this project use short, imperative subjects (`add setup`, `switch to dashscope embeddings`) with optional body lines for context or follow-up tasks. Pull requests should describe scope, list config or dataset changes, and capture the exact verification commands run. Attach screenshots or curl responses whenever API or UI behaviour shifts so reviewers can confirm without reproducing the scenario.

## Security & Configuration Tips
Store secrets solely in `.env` or environment variables and exclude them from logs before commit. After any authentication change, revisit `AUTH_CHECKLIST.md` to confirm token issuance, revocation, and storage obligations remain satisfied.
