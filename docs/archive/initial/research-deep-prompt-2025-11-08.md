# Deep Research Prompt

**Generated:** 2025-11-08
**Created by:** Link
**Target Platform:** Gemini Deep Research

---

## Research Prompt (Ready to Use)

### Research Question

Modern Data Processing Architectures and Legacy System Refactoring Strategies

### Research Goal and Context

**Objective:** Learn modern architecture patterns to inform WorkDataHub brownfield refactoring project

**Context:**
Act as a senior software architect evaluating legacy data processing system refactoring strategies. You're advising a developer who is familiar with ETL patterns but needs to modernize a brownfield data processing project that has become bloated, with tangled architecture and difficult-to-maintain code. Focus on practical, proven patterns that balance modern best practices with real-world migration constraints.

### Scope and Boundaries

**Temporal Scope:** 2023-2025 (modern but battle-tested patterns)

**Geographic Scope:** Global best practices

**Thematic Focus:**
- **INCLUDE:** Data pipeline architectures, refactoring patterns, code organization and modularity, performance and scalability patterns, maintainability and extensibility principles, technology-agnostic design patterns
- **EXCLUDE:** Cloud-specific implementations, real-time streaming systems, big data/distributed systems, machine learning pipelines

### Information Requirements

**Types of Information Needed:**
- Trends and patterns in modern data pipeline architecture
- Technical specifications and design pattern details
- Case studies and real-world refactoring examples
- Comparative analysis of different architectural approaches with trade-offs
- Expert insights and opinions from recognized authorities
- Performance benchmarks and optimization data (where available)

**Preferred Sources:**
- Official technical documentation
- Expert blogs and thought leadership (Martin Fowler, Robert C. Martin, etc.)
- GitHub repositories demonstrating real implementations
- Tech company engineering blogs (Netflix, Uber, Airbnb, Spotify, etc.)
- Technical conference talks (PyCon, QCon, Strange Loop, etc.)
- Stack Overflow and active developer communities
- Established software architecture resources

### Output Structure

**Format:** Executive Summary followed by detailed sections covering: Current challenges in legacy systems → Modern architecture patterns → Refactoring strategies → Best practices → Implementation considerations

**Required Sections:**

1. **Common Problems in Legacy Data Processing Systems**
   - Anti-patterns to avoid
   - Typical pain points in bloated/tangled architectures

2. **Modern Data Pipeline Architecture Patterns**
   - Batch ETL patterns
   - Event-driven architectures
   - Hybrid approaches
   - Layered architectures
   - Each with pros/cons/use cases

3. **Code Organization Strategies**
   - Modular design principles
   - Separation of concerns
   - Dependency management
   - Package/module structure best practices

4. **Refactoring Strategies**
   - Strangler Fig pattern for incremental migration
   - Incremental refactoring approaches
   - Big Bang rewrite trade-offs
   - Risk mitigation strategies

5. **Performance and Scalability Best Practices**
   - Optimization patterns
   - Bottleneck prevention
   - Efficient data processing techniques

6. **Maintainability Principles**
   - Testing strategies for data pipelines
   - Documentation approaches
   - Extensibility patterns
   - Code quality practices

7. **Technology-Agnostic Design Patterns**
   - Patterns applicable regardless of specific tools
   - Repository pattern
   - Clean architecture
   - Hexagonal architecture
   - Dependency injection

8. **Migration Path Recommendations**
   - Step-by-step approaches from legacy to modern
   - Practical transition strategies
   - Risk assessment and mitigation

**Depth Level:** Standard to Comprehensive (1-3 pages per section with practical examples and code snippets where relevant)

### Research Methodology

**Keywords and Technical Terms:**
refactoring patterns, data pipeline architecture, ETL design, modularity, separation of concerns, dependency injection, repository pattern, strangler fig pattern, clean architecture, hexagonal architecture, brownfield refactoring, legacy modernization, incremental migration

**Special Requirements:**
- Include source URLs for all architectural patterns, case studies, and best practices cited
- Prioritize sources from 2023-2025, but include foundational patterns from recognized experts (Fowler, Martin, etc.)
- Present multiple architectural approaches with honest trade-offs - avoid promoting a single "right way"
- Emphasize patterns that can be incrementally adopted in brownfield projects - avoid greenfield-only approaches
- Include code snippets or pseudocode where relevant to illustrate concrete patterns
- Distinguish clearly between FACTS (established patterns), ANALYSIS (interpretations and recommendations), and SPECULATION (emerging trends)

**Validation Criteria:**
- Cross-reference multiple independent sources for key architectural patterns and best practices
- When conflicting viewpoints exist (e.g., "Big Bang Rewrite" vs "Incremental Refactoring"), present BOTH perspectives with their respective trade-offs
- Clearly distinguish between:
  - **FACTS:** Established, well-documented patterns with clear definitions
  - **EXPERT OPINIONS:** Recommendations from recognized authorities in software architecture
  - **SPECULATION:** Emerging trends without substantial track record
- Mark claims with confidence levels: [High Confidence], [Medium Confidence], or [Needs Verification]
- Explicitly highlight gaps or areas where research is limited, contradictory, or requires deeper investigation

### Follow-up Strategy

Potential areas for deeper investigation based on initial findings:

1. **If multiple refactoring strategies emerge:** "Create detailed comparison matrix of incremental vs. big-bang refactoring with risk/effort/timeline trade-offs"

2. **If specific patterns are mentioned but not fully detailed:** "Drill deeper into [Pattern X] with implementation examples and real-world case studies"

3. **If technology choices become relevant:** "Compare Python-based data processing frameworks (Pandas, Polars, DuckDB, etc.) for refactored architecture"

4. **If migration complexity is unclear:** "Provide step-by-step migration roadmap from monolithic to modular data pipeline architecture"

---

## Complete Research Prompt (Copy and Paste)

```
Act as a senior software architect conducting comprehensive research on modern data processing architectures and legacy system refactoring strategies for a developer modernizing a brownfield data processing project.

CONTEXT:
The developer is familiar with ETL patterns but needs to refactor a legacy data processing system that has become bloated, with tangled architecture and difficult-to-maintain code. The goal is to identify practical, proven patterns that balance modern best practices (2023-2025) with real-world migration constraints.

SCOPE:
- Temporal: Focus on 2023-2025 sources (modern but battle-tested)
- Geographic: Global best practices
- INCLUDE: Data pipeline architectures, refactoring patterns, code organization, performance, maintainability, technology-agnostic design
- EXCLUDE: Cloud-specific implementations, real-time streaming, big data/distributed systems, ML pipelines

RESEARCH REQUIREMENTS:

Provide a comprehensive analysis structured as follows:

1. **Executive Summary** (1 page)
   - Key findings and top recommendations

2. **Common Problems in Legacy Data Processing Systems** (1-2 pages)
   - Anti-patterns and typical pain points in bloated architectures
   - What makes legacy systems hard to maintain and extend

3. **Modern Data Pipeline Architecture Patterns** (3-4 pages)
   - Batch ETL patterns
   - Event-driven architectures
   - Hybrid approaches
   - Layered architectures
   - For each: pros, cons, and appropriate use cases

4. **Code Organization Strategies** (2-3 pages)
   - Modular design principles
   - Separation of concerns
   - Dependency management best practices
   - Package/module structure recommendations

5. **Refactoring Strategies** (3-4 pages)
   - Strangler Fig pattern for incremental migration
   - Incremental refactoring approaches
   - Big Bang rewrite (when/why/trade-offs)
   - Risk mitigation strategies
   - Present multiple viewpoints with honest trade-offs

6. **Performance and Scalability Best Practices** (2-3 pages)
   - Optimization patterns
   - Bottleneck prevention
   - Efficient data processing techniques

7. **Maintainability Principles** (2-3 pages)
   - Testing strategies for data pipelines
   - Documentation approaches
   - Extensibility patterns
   - Code quality practices

8. **Technology-Agnostic Design Patterns** (2-3 pages)
   - Repository pattern
   - Clean architecture
   - Hexagonal architecture
   - Dependency injection
   - Patterns applicable across languages/frameworks

9. **Migration Path Recommendations** (2-3 pages)
   - Step-by-step approach from legacy to modern
   - Practical transition strategies for brownfield projects
   - Risk assessment and mitigation

INFORMATION SOURCES - PRIORITIZE:
- Technical documentation (official framework/pattern docs)
- Expert thought leadership (Martin Fowler, Robert C. Martin, etc.)
- Tech company engineering blogs (Netflix, Uber, Airbnb, Spotify)
- GitHub repositories with real implementations
- Technical conferences (PyCon, QCon, Strange Loop)
- Active developer communities

CRITICAL REQUIREMENTS:
✓ Include source URLs for ALL architectural patterns, best practices, and case studies
✓ Cross-reference claims with at least 2 independent sources
✓ When conflicting viewpoints exist, present BOTH with trade-offs (e.g., incremental vs big-bang refactoring)
✓ Clearly label: FACTS (established patterns), EXPERT OPINIONS (recommendations), SPECULATION (emerging trends)
✓ Mark confidence levels: [High Confidence], [Medium Confidence], [Needs Verification]
✓ Include code snippets or pseudocode to illustrate patterns
✓ Emphasize patterns that can be incrementally adopted in brownfield projects
✓ Highlight gaps or areas requiring deeper investigation

KEYWORDS TO EXPLORE:
refactoring patterns, data pipeline architecture, ETL design, modularity, separation of concerns, dependency injection, repository pattern, strangler fig pattern, clean architecture, hexagonal architecture, brownfield refactoring, legacy modernization, incremental migration

OUTPUT:
A comprehensive research report (18-25 pages total) that provides actionable insights for refactoring a legacy data processing system using modern, proven architectural patterns.
```

---

## Platform-Specific Usage Tips

**Gemini Deep Research Tips:**

1. **Keep it simple initially** - Paste the complete prompt above, but Gemini will show you a multi-point research plan before executing

2. **Review the research plan carefully** - Gemini breaks your prompt into specific research questions. This is your chance to:
   - Verify it understood your needs correctly
   - Add missing aspects
   - Remove irrelevant angles
   - Adjust priorities

3. **Be specific and clear** - The prompt above is already well-structured, but if Gemini asks clarifying questions, answer thoroughly

4. **Use follow-up questions strategically** - After initial research completes:
   - "Expand on the Strangler Fig pattern with real-world Python examples"
   - "Create a comparison table of refactoring strategies with effort/risk/timeline"
   - "Drill deeper into testing strategies for data pipelines"

5. **Verify facts when sources seem obscure** - While Gemini cites sources, double-check critical architectural decisions

6. **Available globally in 45+ languages** - Research will be in English based on the prompt

7. **Review before sharing** - The research output is comprehensive - extract the most relevant sections for your PRD

8. **Export/save immediately** - Download the research report before your session expires

---

## Research Execution Checklist

### Before Running Research:

- [ ] Prompt clearly states the research question ✓
- [ ] Scope and boundaries are well-defined ✓
- [ ] Output format and structure specified ✓
- [ ] Keywords and technical terms included ✓
- [ ] Source guidance provided ✓
- [ ] Validation criteria clear (anti-hallucination measures) ✓
- [ ] Target platform confirmed (Gemini Deep Research) ✓

### During Research:

- [ ] Review Gemini's research plan before it starts searching
- [ ] Verify the plan covers all 8 required sections
- [ ] Check that temporal scope (2023-2025) is understood
- [ ] Confirm exclusions are clear (cloud-specific, streaming, big data, ML)
- [ ] Answer any clarifying questions Gemini asks thoroughly
- [ ] Monitor if Gemini provides a progress indicator
- [ ] Take notes on unexpected findings or gaps that emerge

### After Research Completion:

- [ ] Verify key architectural patterns are cited with source URLs
- [ ] Check that 2+ sources support critical recommendations
- [ ] Identify any conflicting information and how it was resolved
- [ ] Confirm confidence levels are marked for major claims
- [ ] Review code examples for relevance and accuracy
- [ ] Identify gaps requiring follow-up research
- [ ] Ask clarifying follow-up questions:
  - "Can you provide more Python-specific examples for [Pattern X]?"
  - "What are the risks of incremental migration vs big-bang rewrite?"
  - "Which patterns are most suitable for a brownfield refactoring?"
- [ ] Export/download the complete research report
- [ ] Save to your WorkDataHub documentation folder
- [ ] Extract key insights to inform your PRD

### Post-Research Actions:

- [ ] Create summary of top 5-7 architectural recommendations
- [ ] Identify 2-3 refactoring strategies most suitable for WorkDataHub
- [ ] Document technology-agnostic patterns to adopt
- [ ] Flag areas needing additional research or clarification
- [ ] Use findings to inform PRD creation (next workflow step)

---

## Metadata

**Workflow:** BMad Research Workflow - Deep Research Prompt Generator v2.0
**Generated:** 2025-11-08
**Research Type:** Deep Research Prompt
**Platform:** Gemini Deep Research
**Project:** WorkDataHub
**Purpose:** Inform brownfield refactoring PRD with modern architecture patterns

---

_This research prompt was generated using the BMad Method Research Workflow, incorporating best practices from ChatGPT Deep Research, Gemini Deep Research, Grok DeepSearch, and Claude Projects (2025)._
