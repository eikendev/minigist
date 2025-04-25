# Coding Standards

## Code Clarity & Style

- Use **meaningful names** for variables, functions, and classes
- Keep functions and methods short and focused (one purpose / responsibility)
- Follow **PEP 8** guidelines for style
- Use **type hints** for better clarity and static analysis
- Add **docstrings** to modules, classes, functions, and methods to explain their purpose, arguments, and return values
- Add **inline comments** only when strictly necessary to explain complex logic that isn't clear from the code itself

## Input Validation & Sanitization

- Validate and sanitize **all external inputs**, such as command-line arguments or data from external APIs

## Security Practices

- Never log passwords, API keys, or other sensitive data
- Use environment variables or a secure configuration management system for secrets; never commit them directly to the repository

## Tests & Coverage

- Write tests using **pytest**
- Test edge cases and error conditions, not just the "happy path"
- Keep tests deterministic, independent, and reasonably fast
- Aim for clear and expressive assertions

## Simplicity First

- Prioritize **simple, clear, and maintainable** code over overly complex or "clever" solutions
- Follow the Zen of Python (`import this`)
