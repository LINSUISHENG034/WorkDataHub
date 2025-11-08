# Legacy Codebase

**IMPORTANT:** This directory contains the full codebase from the previous iteration of WorkDataHub. It serves as the reference baseline for the ongoing reimplementation.

## Purpose
- Preserve legacy behavior for comparison and regression checks.
- Document known patterns and decisions that must be carried forward or replaced.
- Provide a safety net while modernizing architecture and tooling.

## Expectations for the new implementation
- Achieve functional parity with the legacy system before adding new features.
- Improve modularity, decoupling, and overall extensibility.
- Address known pain points in performance, maintainability, and deployment.

## Recommended workflow
1. Use the legacy modules as a reference when clarifying expected inputs, outputs, and edge cases.
2. Capture differences discovered during reimplementation in the main project documentation or architecture decision records.
3. Avoid modifying this directory directly; changes should be made in the new codebase while keeping the legacy snapshot intact.

## Additional notes
- Treat this code as read-only unless a specific fix is required to unblock parity validation.
- Highlight any missing assets or external dependencies in the new project backlog so they are tracked explicitly.