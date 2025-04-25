# Behavior Guidelines

## General Guidance

- Prefer asking for clarification if context appears missing or ambiguous
- Identify any **assumptions** you're making before proceeding with changes or recommendations

## Task Execution

- Before writing code:
  1. Analyze **all relevant** code files
  2. Extract existing patterns and conventions
  3. Suggest an implementation plan in Markdown
  4. Only then, proceed to write actual code

- Do not propose refactors unless:
  - There's clear duplication
  - Complexity thresholds are exceeded (e.g., long methods, nested logic)
  - The suggestion improves maintainability without breaking conventions

## Style & Completeness

- Always return **complete** function/class/module implementations unless otherwise requested
- Avoid truncation and include **all** required dependencies or imports in generated code

## Testing Suggestions

- When modifying business logic, suggest matching unit tests
- For endpoint changes, recommend or generate integration test updates
- Mention potential test fallout when editing shared or central components
