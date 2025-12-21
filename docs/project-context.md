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

## ✨ Zero Legacy Policy (Pre-Production Phase)

**Context:** Since the project is strictly in the **Pre-Production** phase, maintaining backward compatibility creates unnecessary technical debt and bloat.

**Core Principle:**
Prioritize **Clean Architecture** and **Code Readability** over backward compatibility. We do not support "deprecated" methods or classes.

**Execution Standards:**

1.  ** ⚛️ Refactor Fearlessly, but Atomically:**
    * If an architectural decision changes (e.g., function signature, class responsibility), **DO NOT** create a wrapper or an overload to support the old usage.
    * **Action:** Change the definition AND update **all** call sites immediately within the same iteration. The codebase must remain compilable/runnable after the change.

2.  ** 🗑️ No Dead Code:**
    * Delete commented-out code, unused files, or "v1" implementations immediately. Do not keep them "just in case." (We have Git for history).

3.  ** 🗄️ Schema Changes:**
    * If data models change, prefer updating the schema and seeding scripts (reset strategy) over writing complex migration scripts, unless explicitly instructed otherwise.

4.  ** 📉 Simplicity Over Stability:**
    * It is better to break the build temporarily to achieve a cleaner design than to introduce complexity to keep a bad design working.

## 🚨 CRITICAL: Shell Command Standards

### 1. For Agents using "Bash Tool" (Unix/Linux/WSL)
**IMPORTANT:** If the agent is using a specific **Bash Tool** (common in Claude Code), it executes **Unix/bash commands** even on Windows.

**This means:**
- ✅ Use Unix commands: `rm`, `ls`, `cp`, `mv`, `test`, `mkdir -p`
- 🚫 DO NOT use Windows CMD: `del`, `dir`, `copy`, `move`, `if exist`
- 🛠️ Prefer specialized tools (Read, Write, Edit) over bash for file operations

**Examples of common mistakes (Bash):**
```bash
# ❌ WRONG - Windows CMD syntax (will fail in Bash)
if exist "file.txt" del "file.txt"

# ✅ CORRECT - Unix bash syntax
test -f "file.txt" && rm "file.txt"
```

### 2. For Agents using "PowerShell" (Windows Native)
**IMPORTANT:** If the agent is operating natively on **Windows** (e.g., Gemini CLI) and executes commands via **PowerShell**.

**This means:**
- ✅ Use PowerShell cmdlets or common aliases: `Remove-Item` (rm), `Get-ChildItem` (ls), `Copy-Item` (cp), `Move-Item` (mv), `Test-Path`.
- 🚫 DO NOT use Unix/Bash specific syntax (like `export`, `source`, `[ -f ... ]`) unless in WSL.
- 🛠️ Prefer specialized tools (`read_file`, `write_file`, `replace`) over shell commands for file operations.

**Examples (PowerShell):**
```powershell
# ✅ CORRECT - PowerShell syntax
if (Test-Path "file.txt") { Remove-Item "file.txt" }
```

# 🏆 BEST - Use specialized tools
# Use read_file to read files
# Use write_file to create files
# Use replace to modify files
```

---

## 🐍 Project Environment Management: Using `uv` (For Senior Developers)

* ** ⚡ Tool:** This project utilizes **`uv`** for ultra-fast package and virtual environment management.
* ** ⚙️ Execution Standard:** All Python script execution *must* be performed using **`PYTHONPATH=src uv run`** to ensure the correct environment and dependencies are loaded.

### 🛠️ Environment Configuration
* **Simplify Commands:** Use the `--env-file .wdh_env` flag with `uv run` to load project configurations automatically, avoiding verbose argument lists.
  ```bash
  uv run --env-file .wdh_env src/script.py
  ```
* ** 🔋 Shell Activation:** You may also manually load the environment (e.g., `source .wdh_env` or PowerShell equivalent) to activate configuration for the current session.

> ** 🔑 Key Action:** Always use `uv run` (preferably with `--env-file .wdh_env`) for running scripts. Avoid direct `python` calls.

---

## File and Function Limits

- **Never create a file longer than 500 lines of code**. If approaching this limit, refactor by splitting into modules.
- **Functions should be under 50 lines** with a single, clear responsibility.
- **Classes should be under 100 lines** and represent a single concept or entity.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
- **Line lenght should be max 100 characters** ruff rule in pyproject.toml

---

