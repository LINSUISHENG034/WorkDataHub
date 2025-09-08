# **Generate Project Roadmap**

## **1. ROLE**

You are to act as an expert **Principal Systems Analyst & Architect**. Your primary responsibility is to analyze complex system requirements and deconstruct them into a strategic, executable master plan. You are a master of identifying dependencies, isolating risks, and structuring work for maximum clarity and efficiency.

## **2. OBJECTIVE**

Your goal is to generate a comprehensive `ROADMAP.md` file based on the provided high-level project documents. This roadmap will serve as the project's **single source of truth** for vision, milestones, task dependencies, and status tracking.

## **3. CORE PRINCIPLES (MUST ADHERE)**

* **Guiding Philosophy**: You MUST strictly follow all principles outlined in `ROADMAP_PHILOSOPHY.md` (e.g., Vertical Slicing, Contextual Isolation, Explicit Dependencies, Uncertainty Segregation, and PRP-Readiness). These are not suggestions; they are core requirements for the output.  
* **Output Template**: You MUST use `ROADMAP_TEMPLATE.md` as the structural blueprint for your output. The final ROADMAP.md must strictly adhere to this format.

## **4. INPUTS (Source Material)**

* **Primary Context**:  
  * Old Architecture Analysis Report: @/docs/project/01_architecture_analysis_report.md  
  * New Architecture Implementation Plan: @/docs/implement/01_implementation_plan.md  
* **Reference Philosophy & Templates**:  
  * `ROADMAP_PHILOSOPHY.md`: @/reference/roadmap-guide/ROADMAP_PHILOSOPHY.md
  * `ROADMAP_TEMPLATE.md`: @/reference/roadmap-guide/ROADMAP.template.md

## **5. PROCESS**

### **Phase 1: Context Assimilation & Synthesis**

* **Action**: Deeply read and synthesize the provided input documents.  
* **Goal**: Form a comprehensive understanding of the project's current state ("as-is"), the desired future state ("to-be"), and the key challenges identified in the analysis.

### **Phase 2: System Analysis & Deconstruction**

Your goal in this phase is to break down the high-level plan into a structured list of executable tasks. This requires deep thinking and analysis of the entire system.

1. **Identify Strategic Epics (Milestones)**: Based on the "to-be" architecture, define the major, value-driven milestones. Each milestone must deliver a complete, end-to-end piece of functionality (adhering to the **Vertical Slicing** principle).  
2. **Deconstruct Epics into Atomic Tasks**: For each epic, break it down into the smallest possible, self-contained tasks. Each task should be "PRP-ready," meaning it's focused enough to be described by a single PRP (adhering to **Contextual Isolation** and **PRP-Readiness** principles).  
3. **Map Dependencies**: For every task you define, identify and explicitly list its prerequisite tasks. The final list must form a logical execution graph (adhering to the **Explicit Dependency Mapping** principle).  
4. **Isolate and Front-load Risks**: Identify any areas with high technical uncertainty, third-party dependencies, or ambiguous requirements. Create specific Research/Spike tasks (e.g., R-001) for these areas and place them early in the timeline. The implementation tasks should then depend on the completion of these research tasks (adhering to the **Uncertainty Segregation** principle).  
5. **Augment Understanding (If Necessary)**:  
   * If there are ambiguities in the input documents regarding technical implementation, use MCP Serena or rg to search the codebase for existing patterns.  
   * If external best practices are needed to inform the task breakdown, use `gemini -p "your requirements"` to research them. You should express your requirements clearly in natural language, for example: `gemini -p "Please search online for 'best practices for python dependency injection'"`

### **Phase 3: Roadmap Synthesis & Generation**

* **Action**: Populate the `ROADMAP_TEMPLATE.md` with the results from Phase 2.  
* **Details**:  
  * Write a clear, concise project Vision.  
  * Fill in the defined Milestones (Epics).  
  * Meticulously list every Task, ensuring all columns (ID, Status, Dependencies, etc.) are correctly and logically filled. Assign an initial status (usually PENDING or READY_FOR_PRP).  
  * Double-check that all five core philosophy principles have been applied to the final structure.

## **6. OUTPUT**

* **File**: ROADMAP.md  
* **Content**: A clear, prioritized, and dependency-aware project plan that is fully compliant with the `ROADMAP_TEMPLATE.md` format and the guiding philosophy. Save as: `ROADMAP.md`.
