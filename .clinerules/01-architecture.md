# Project Architecture

`minigist` is a command-line interface application built with Python.

## Structure

- `/minigist`: Main application source code
    - `cli.py`: Main CLI entry point and command definitions (using Click).
    - `config.py`: Handles loading and validation of configuration.
    - `miniflux_client.py`: Interacts with the Miniflux API.
    - `summarizer.py`: Fetches article content and generates summaries.
    - `processor.py`: Orchestrates the main workflow.
    - `notification.py`: Sends notifications via Apprise.
    - `models.py`: Defines data models.
    - `logging.py`: Configures structured logging.
    - `exceptions.py`: Defines custom exceptions.
    - `constants.py`: Defines application-wide constants.

## Key Technologies

- **Click**: Framework for building the CLI
- **Pydantic**: Configuration modeling and validation
- **PyYAML**: Loading YAML configuration
- **miniflux**: Miniflux API client library
- **newspaper3k**: Article content extraction
- **structlog**: Structured logging
- **Apprise**: Notification delivery
