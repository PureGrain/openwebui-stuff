# Copilot Instructions for openwebui-stuff

This guide helps AI coding agents work productively in the `openwebui-stuff` codebase. It summarizes key architecture, workflows, and conventions unique to this project.

## Project Overview
- **Purpose:** Central hub for OpenWebUI tools, models, and functions.
- **Structure:**
  - `functions/` — (currently empty) Intended for utility or core logic modules.
  - `models/` — (currently empty) Intended for ML models or data abstractions.
  - `prompts/` — (currently empty) Intended for prompt templates or prompt engineering assets.
  - `tools/` — Contains `timeweaver.py`, likely a specialized tool or script.

## Key Patterns & Conventions
- **Modularity:** Each top-level directory is for a distinct concern (functions, models, prompts, tools).
- **Naming:** Files and folders use lowercase and descriptive names.
- **Extensibility:** Empty folders signal planned expansion; add new modules following the existing structure.

## Developer Workflows
- **No build/test scripts detected.**
  - If adding build or test workflows, place scripts in the project root or a dedicated `scripts/` folder.
- **Debugging:** For Python tools (e.g., `tools/timeweaver.py`), run directly with `python tools/timeweaver.py`.

## Integration Points
- **External dependencies:** Not detected in the current structure. Add requirements to a `requirements.txt` in the root if needed.
- **Cross-component communication:** Organize shared logic in `functions/`, models in `models/`, and prompts in `prompts/` for clarity.

## Example: Adding a New Tool
1. Place new scripts in `tools/`.
2. Use clear, descriptive filenames (e.g., `data_cleaner.py`).
3. Document usage in the README or in a dedicated docstring.

## References
- See `README.md` for a brief project description.
- Use this file to update AI agent instructions as the project evolves.

---
*Update this file whenever major architectural or workflow changes occur.*
