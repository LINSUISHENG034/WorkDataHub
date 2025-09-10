# Create PRP v2.03

---
argument-hint: [feature-file] [id-prefix]
description: Generate a complete PRP
---

## Context

Parse $ARGUMENTS to get the following values:
[feature-file]: $1 from $ARGUMENTS
[id-prefix]: $2 from $ARGUMENTS. If null, use the next sequential number based on the naming pattern in the `PRPs/` directory.

Generate a complete PRP for general feature implementation with thorough research. Ensure context is passed to the AI agent to enable self-validation and iterative refinement. Read the [feature-file] first to understand what needs to be created, how the examples provided help, and any other considerations.

The AI agent only gets the context you are appending to the PRP and training data. Assuma the AI agent has access to the codebase and the same knowledge cutoff as you, so its important that your research findings are included or referenced in the PRP. The Agent has Websearch capabilities, so pass urls to documentation and examples.

## Research Process

1. **Codebase Analysis**
   - Search for similar features/patterns in the codebase
   - Identify files to reference in PRP
   - Note existing conventions to follow
   - Check test patterns for validation approach

2. **External Research**
   - **Leverage AI for Efficient Research**: Use the `gemini -p '...'` command to accelerate online research. Ensure your prompts are clear and goal-oriented.
      - **For Pattern Discovery**: When exploring general solutions or best practices, state your requirements clearly.
      - **e.g.**, `gemini -p 'Search online for best practices for Python dependency injection.'`

      - **For Documentation Analysis**: When dealing with specific libraries or APIs, provide a URL for the AI to summarize and analyze. This is crucial for obtaining the latest information.
      - **e.g.**, `gemini -p 'Summarize the usage of validation decorators in Pydantic from <URL> and provide a simple code example.'`

   - Library documentation (include specific URLs)
   - Implementation examples (GitHub/StackOverflow/blogs)
   - Best practices and common pitfalls

   - Persist research for implementation phase: When findings will inform API usage, environment/config, version pinning, or validation steps, record them directly in the PRP under a dedicated "Implementation-Facing Research Notes" section. Include:
     - Source URL(s) and precise anchors/sections
     - TL;DR summary (3–5 bullets)
     - Required setup/commands/snippets (copy-pasteable)
     - API/parameter decisions with rationale
     - Version constraints and compatibility notes
     - Known pitfalls/edge cases and mitigations
     - Open questions to clarify before execution
   - Do not defer with "will research later"; capture the minimum actionable context so the executing agent does not need to repeat the search.

3. **User Clarification** (if needed)
   - Specific patterns to mirror and where to find them?
   - Integration requirements and where to find them?

## PRP Generation

Using PRPs/templates/prp_base.md as template:

### Critical Context to Include and pass to the AI agent as part of the PRP

- **Documentation**: URLs with specific sections
- **Code Examples**: Real snippets from codebase
- **Gotchas**: Library quirks, version issues
- **Patterns**: Existing approaches to follow
- **External Research Findings**: Actionable notes with links, setup commands, version constraints, pitfalls, and open questions for execution

### Implementation Blueprint

- Start with pseudocode showing approach
- Reference real files for patterns
- Include error handling strategy
- list tasks to be completed to fullfill the PRP in the order they should be completed

### Validation Gates (Must be Executable) eg for python

```bash
# Syntax/Style
ruff check --fix && mypy .

# Unit Tests
uv run pytest tests/ -v

```

### Quality Benchmark Example

Before generating the PRP, **analyze** the completed example at PRPs/templates/EXAMPLE_multi_agent_prp.md . **Emulate its structure and level of detail** to ensure your output meets the quality standard.

*** CRITICAL AFTER YOU ARE DONE RESEARCHING AND EXPLORING THE CODEBASE BEFORE YOU START WRITING THE PRP ***

*** ULTRATHINK ABOUT THE PRP AND PLAN YOUR APPROACH THEN START WRITING THE PRP ***

## Output

Save as: `PRPs/{[id-prefix]}.md`

## Quality Checklist

- [ ] All necessary context included
- [ ] Validation gates are executable by AI
- [ ] References existing patterns
- [ ] Clear implementation path
- [ ] Error handling documented
 - [ ] External research captured for reuse (actionable notes + links)

Score the PRP on a scale of 1-10 (confidence level to succeed in one-pass implementation using claude codes)

Remember: The goal is one-pass implementation success through comprehensive context.
