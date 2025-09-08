# **Project: \[Project Name\]**

## **Vision**

\<\!--  
BRIEFLY state the high-level goal of the project. This provides overarching context for all epics and tasks.  
Example: "To build an automated research assistant that can search the web and draft emails."  
\--\>

## **Milestone 1: \[Name of First Major Value-Driven Epic\]**

\<\!--  
PHILOSOPHY: This aligns with "Pillar 1: Vertical Slicing". Each milestone should represent a complete, demonstrable piece of functionality.  
EXAMPLE: "M1: Core User Authentication" is a good vertical slice. "M1: Build Database Layer" is a bad horizontal slice.  
\--\>

| ID | Epic | Feature/Task | Status | Dependencies | PRP\_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| R-001 | M1 | Research SSO Integration Options | COMPLETED | \- | R-001 |
| F-001 | M1 | Implement User Registration API | PRP\_GENERATED | R-001 | F-001 |
| F-002 | M1 | Implement User Login API | READY\_FOR\_PRP | R-001, F-001 | \- |
| F-003 | M1 | Implement "Forgot Password" Flow | PENDING | F-001 | \- |

\<\!--  
TASK BREAKDOWN PHILOSOPHY:

* **Contextual Isolation (Pillar 2\)**: "User Registration" and "User Login" are separate tasks because their contexts are distinct.  
* **Uncertainty Segregation (Pillar 4\)**: The "SSO Integration" was identified as a risk and handled by a research task (R-001) first. Its output informs the implementation tasks.  
* **Explicit Dependencies (Pillar 3\)**: F-002 cannot start until both the research (R-001) and the core registration (F-001) are done.  
* PRP-Readiness (Pillar 5): Each task (F-001, F-002) is small enough to be described by a single PRP and completed in a short cycle.  
  \--\>

## **Milestone 2: \[Name of Second Major Value-Driven Epic\]**

| ID | Epic | Feature/Task | Status | Dependencies | PRP\_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| F-004 | M2 | Display User Profile Page | PENDING | F-002 | \- |
| F-005 | M2 | Allow User to Update Profile | PENDING | F-004 | \- |

\<\!-- Add more milestones as needed \--\>

## **Key**

### **ID Prefix**

* **F-XXX**: Feature Implementation Task  
* **R-XXX**: Research / Spike Task  
* **C-XXX**: Chore / Refactoring Task

### **Status Lifecycle**

1. PENDING: Planned but not ready.  
2. READY\_FOR\_PRP: All dependencies are COMPLETED. Ready for PRP generation.  
3. PRP\_GENERATED: PRP is created and linked. Ready for an execution agent.  
4. IN\_PROGRESS: An agent is actively working on the task.  
5. VALIDATING: Code is complete, agent is running validation loops.  
6. COMPLETED: All validation gates passed.  
7. BLOCKED: Progress is impeded. Requires human review.
