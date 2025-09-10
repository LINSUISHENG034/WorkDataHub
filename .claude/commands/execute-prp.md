# Execute BASE PRP v1.02

Implement a feature using using the PRP file.

## PRP File: $ARGUMENTS

## Execution Process

1. **Load PRP**
   - Read the specified PRP file
   - Understand all context and requirements
   - Follow all instructions in the PRP and extend the research if needed
   - Ensure you have all needed context to implement the PRP fully
   - **Leverage AI for Efficient Research**: Use the `gemini -p '...'` command to accelerate online research. Ensure your prompts are clear and goal-oriented.
      - **For Pattern Discovery**: When exploring general solutions or best practices, state your requirements clearly.
      - **e.g.**, `gemini -p 'Search online for best practices for Python dependency injection.'`

      - **For Documentation Analysis**: When dealing with specific libraries or APIs, provide a URL for the AI to summarize and analyze. This is crucial for obtaining the latest information.
      - **e.g.**, `gemini -p 'Summarize the usage of validation decorators in Pydantic from <URL> and provide a simple code example.'`

2. **ULTRATHINK**
   - Think hard before you execute the plan. Create a comprehensive plan addressing all requirements.
   - Break down complex tasks into smaller, manageable steps using your todos tools.
   - Use the TodoWrite tool to create and track your implementation plan.
   - Identify implementation patterns from existing code to follow.

3. **Execute the plan**
   - Execute the PRP
   - Implement all the code

4. **Validate**
   - Run each validation command
   - Fix any failures
   - Re-run until all pass

5. **Complete**
   - Ensure all checklist items done
   - Run final validation suite
   - Report completion status
   - Read the PRP again to ensure you have implemented everything

6. **Reference the PRP**
   - You can always reference the PRP again if needed

Note: If validation fails, use error patterns in PRP to fix and retry.