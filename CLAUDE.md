# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **📚 Detailed Standards:** See [`docs/project-context.md`](docs/project-context.md) for complete development standards, architecture documentation, CLI reference, and domain terminology.

## Project Context Protocol:
1. **Environment**: Always load config from `.wdh_env`. DO NOT guess credentials.
2. **Dual-DB Constraint**: 'Legacy' refers to the schema in Postgres (migrated from MySQL). 'New' refers to the `annuity_performance` domain logic.
3. **Migration Rule**: All schema changes must be via Alembic. Direct DDL is forbidden unless explicitly requested for debugging.
4. **Zero Legacy Debt**: Do not import any code from `legacy/` directory into `src/`. Re-implement logic only.”

## Core Development Philosophy

### KISS (Keep It Simple, Stupid)

Simplicity should be a key goal in design. Choose straightforward solutions over complex ones whenever possible. Simple solutions are easier to understand, maintain, and debug.

### YAGNI (You Aren't Gonna Need It)

Avoid building functionality on speculation. Implement features only when they are needed, not when you anticipate they might be useful in the future.

### Design Principles

- **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Open/Closed Principle**: Software entities should be open for extension but closed for modification.
- **Single Responsibility**: Each function, class, and module should have one clear purpose.
- **Fail Fast**: Check for potential errors early and raise exceptions immediately when issues occur.

## ⚠️ CRITICAL: Bash Tool Uses Unix Commands

**IMPORTANT:** Even on Windows, the Bash tool in Claude Code executes **Unix/bash commands**, NOT Windows CMD or PowerShell commands.

**This means:**
- ✅ Use Unix commands: `rm`, `ls`, `cp`, `mv`, `test`, `mkdir -p`
- ❌ DO NOT use Windows CMD: `del`, `dir`, `copy`, `move`, `if exist`
- 🎯 Prefer specialized tools (Read, Write, Edit) over bash for file operations

**Examples of common mistakes:**
```bash
# ❌ WRONG - Windows CMD syntax (will fail)
if exist "file.txt" del "file.txt"
dir /b
copy source.txt dest.txt

# ✅ CORRECT - Unix bash syntax
test -f "file.txt" && rm "file.txt"
# or
[ -f "file.txt" ] && rm "file.txt"
ls
cp source.txt dest.txt

# 🎯 BEST - Use specialized tools
# Use Read tool to read files
# Use Write tool to create files
# Use Edit tool to modify files
```

---

## 🛠️ Project Environment Management: Using `uv` (For Senior Developers)

* **Tool:** This project utilizes **`uv`** for ultra-fast package and virtual environment management.
* **Execution Standard:** All Python script execution *must* be performed using **`PYTHONPATH=src uv run`** to ensure the correct environment and dependencies are loaded.

> **Key Action:** Always use `uv run --with [PATH]` for running scripts. Avoid direct `python` calls.

---

