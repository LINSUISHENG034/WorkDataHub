# **AGENTS.md (v2.0 with Roadmap Integration)**

This file is a README for agents. It gives any AI coding assistant a predictable, minimal set of rules and commands to work effectively in this repository, from high-level project planning to low-level code implementation.

## **🗺️ The Three-Layer Development Workflow**

Our development process follows a structured, three-layer model to ensure clarity, traceability, and efficient execution.

1. **L1: Strategy (ROADMAP.md)**: The project's master plan. It defines the vision, milestones, and the dependency graph of all features. **This is the single source of truth for project status.**  
2. **L2: Tactic (INITIAL.md)**: The readiness checklist for a single task identified in the ROADMAP.md. It gathers all necessary context before implementation begins.  
3. **L3: Execution (PRPs/\<feature\>.md)**: The detailed, step-by-step implementation blueprint for an AI agent to execute a task.

## **🔁 The Integrated Development Cycle**

### **Stage 0: Strategic Planning (Human-led)**

* **Action**: Define the project vision, milestones, and tasks in ROADMAP.md.  
* **Philosophy**: Follow the principles outlined in ROADMAP\_PHILOSOPHY.md (Vertical Slicing, Contextual Isolation, etc.).  
* **Outcome**: A clear, prioritized, and dependency-aware project plan.

### **Stage 1: Task Preparation (The "Plan" in Plan → Execute → Prove)**

1. **Select a Task**: A human developer or a planning agent identifies a task in ROADMAP.md with the status READY\_FOR\_PRP.  
2. **Prepare INITIAL.md**: Create or update INITIAL.md based on the selected task's requirements. This is the "Definition of Ready".  
   * Define the feature and boundaries (non‑goals).  
   * Add concrete examples: existing files, code snippets, or patterns to follow.  
   * Link precise external docs (URLs, sections) and internal standards (file paths).  
   * Do more web searches and codebase exploration as needed; Use gemini \-p "your requirements" for web searches.  
   * Note integration points: data models, APIs, migrations, configs.  
   * Call out gotchas: library quirks, rate limits, concurrency/timeouts, version traps.  
   * Include validation commands and expected outcomes.  
   * Start from template: PRPs/templates/INITIAL.template.md  
3. **Generate PRP**:  
   * Use /generate-prp INITIAL.md \<ID\> (e.g., /generate-prp INITIAL.md F-001). The ID is crucial for traceability.  
   * The agent reads INITIAL.md, generates PRPs/F-001.md.  
   * **Crucially, the agent must then update ROADMAP.md**: change the status of F-001 to PRP\_GENERATED and add the link to the new PRP file.

### **Stage 2: Task Implementation (The "Execute" and "Prove")**

1. **Fetch a Task**: An execution agent queries ROADMAP.md for a task with the status PRP\_GENERATED.  
2. **Execute PRP**:  
   * Use /execute-prp PRPs/\<feature-name\>.md.  
   * **Before starting, the agent must update ROADMAP.md**: change the task status to IN\_PROGRESS.  
3. **Validation Gates (Definition of Done)**:  
   * The agent follows the validation steps in the PRP. As it enters the validation phase, it updates the status to VALIDATING.  
   * All checks must pass before marking complete:  
     * uv run ruff check src/ \--fix  
     * uv run mypy src/  
     * uv run pytest \-v  
   * Add/adjust tests so critical paths are covered; fix failures, re‑run gates to green.  
   * Update documentation impacted by the change.  
4. **Finalize Task**:  
   * Once all gates are green, **the agent's final action is to update ROADMAP.md**: change the task status to COMPLETED.

## **🛠️ Key Files and Commands**

* **ROADMAP.md**: The master plan. The first place to look to understand the project's progress and what to work on next.  
* INITIAL.md: Seed file for a **single task** from the Roadmap.  
* PRPs/: Stores generated implementation blueprints.  
* CLAUDE.md: Project‑specific rules (style, structure, tooling, etc.).  
* .claude/commands/: Location of slash command definitions.

\<\!-- The rest of the sections (Development Tips, Testing & Linting, Pull Requests, etc.) remain largely the same as they define the low-level execution standards. \--\>

## **Development Tips**

* **Package Management:** uv for all dependency and virtual environment management.  
* **WSL**: source .venv\_linux/bin/activate; **PowerShell**: .\\.venv\\Scripts\\Activate.ps1; **CMD**: .\\.venv\\Scripts\\activate.bat.  
* Use uv for everything: uv venv && uv sync to set up; run tools via uv run ....  
* Search fast: prioritize using MCP Serena. As an alternative, prefer rg (ripgrep) over grep/find for code and files.  
* Keep changes small and focused; follow existing patterns and conventions.

## **Testing & Linting (Python)**

* Lint: uv run ruff check src/ \--fix  
* Type check: uv run mypy src/  
* Tests: uv run pytest \-v (use \-k \<pattern\> to focus)  
* Optional coverage: uv run pytest \--cov=src \--cov-report=term-missing

## **Pull Requests**

* Branch naming: feature/\<name\>, fix/\<name\>, docs/\<name\>.  
* Before commit: run lint, type check, tests locally; keep commits scoped.  
* Commit message style: conventional commits (\<type\>(\<scope\>): \<subject\>). See CLAUDE.md for project specifics.  
* PR description: summarize the change, link issues, note any migrations/flags.

## **Assistant Notes**

* If your assistant supports custom commands, prefer the commands above; otherwise copy the command file contents into your prompt with the appropriate arguments.  
* Keep instructions concrete and runnable; prefer the shortest viable commands.  
* Ask for clarification when requirements are ambiguous; do not guess.