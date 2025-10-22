# Repository Guidelines

## Project Structure & Module Organization
Core Python packages live under `are/simulation/`: `core/` orchestrates environments, `agents/` implements agent policies, `apps/` exposes task-specific interfaces, and `scenarios/` bundles sample universes. Shared utilities (e.g., `tool_box.py`, `utils/`) sit beside them. GUI assets are in `are/simulation/gui/` with the React client in `gui/client/`. Tests mirror the source tree in `are/simulation/tests/`, while documentation sources live in `docs/`. Configuration helpers (`pyproject.toml`, `pyrightconfig.json`, `build_hooks/`) anchor the repository root.

## Build, Test, and Development Commands
- `uv sync --extra dev` installs runtime plus dev tooling from `pyproject.toml`.
- `uvx are-run -s scenario_tutorial -a default` runs a tutorial scenario locally.
- `uvx are-benchmark gaia2-run --hf meta-agents-research-environments/gaia2 --hf_split validation -l 1` exercises the Gaia2 benchmark sampler.
- `uv run --extra dev pytest are/simulation/tests` executes the full Python test suite.
- `uvx ruff check --fix .` and `uvx ruff format .` lint and format Python code; `uv run --extra dev pyright` performs static type checks.
- For GUI changes, run `npm install` then `npm run tsc` inside `are/simulation/gui/client/`.

## Coding Style & Naming Conventions
Python code targets 3.12, uses Ruff for linting/formatting, and Pyright for type safety; keep imports sorted and prefer modern typing (`list[int]`). Follow existing naming patterns: snake_case for modules/functions, PascalCase for classes, and suffix new tests with `_test.py`. TypeScript in the GUI follows Prettier defaults and `npm run format` enforces spacing and semicolons. Maintain focused modules and reuse helpers from `utils/` or `tool_utils.py` instead of duplicating logic.

## Testing Guidelines
Write pytest-based tests under the matching tree in `are/simulation/tests/` (e.g., tests for `apps/filesystem.py` belong in `tests/apps/`). Use descriptive test names like `test_handles_missing_attachment`. Mark slow or environment-specific cases with `@pytest.mark.skipif` similar to existing patterns. For new scenarios or agents, add regression coverage that verifies orchestration via `ScenarioRunner` or the relevant app client. Ensure CI-critical suites (`pytest`, `ruff`, `pyright`) pass before submitting.

## Commit & Pull Request Guidelines
Commit messages follow short, present-tense summaries (`fix streaming_utils tests`, `update pyproject to avoid building enormous wheels`). Group related changes and avoid bundling refactors with behavioral updates. Pull requests should link tracked issues, describe scenario or agent impacts, and include before/after metrics or CLI commands when behavior changes. Mention required environment variables (e.g., Hugging Face credentials) in the PR description, and attach screenshots for GUI updates when applicable.

## Agent & Scenario Tips
Agent configs live under `are/simulation/agents/` with reusable defaults in `config.py`. When introducing new scenarios, copy the structure from `scenarios/tutorials/`, ensure assets reside in `data/`, and register them via `scenario_runner.py`. Keep deterministic seeds and validation logic in sync so benchmark runs stay reproducible.
