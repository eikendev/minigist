<div align="center">
	<h1>minigist</h1>
	<h4 align="center">
		AI-powered summaries for your <a href="https://miniflux.app/">Miniflux</a> feeds.
	</h4>
	<p>Turn your long Miniflux articles into clear, concise summaries.</p>
</div>

<p align="center">
	<a href="https://github.com/eikendev/minigist/actions"><img alt="Build status" src="https://img.shields.io/github/actions/workflow/status/eikendev/minigist/main.yml?branch=main"/></a>&nbsp;
	<a href="https://github.com/eikendev/minigist/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/eikendev/minigist"/></a>&nbsp;
	<a href="https://pypi.org/project/minigist/"><img alt="PyPI" src="https://img.shields.io/pypi/v/minigist"/></a>&nbsp;
</p>

## ✨&nbsp;Why minigist?

Long-form feed entries are great for depth but hard to keep up with. Miniflux shows the full content, and without a summary layer you still have to read everything to decide what matters.

minigist solves this by generating concise summaries on the server side and writing them directly into each unread entry. This works with your current way to read Miniflux entries, no client changes needed.

## 🧠&nbsp;How it works

- You define prompts and targets in a YAML config file
- minigist fetches the full text of unread entries (using pure.md if configured)
- Your configured LLM generates summaries using your prompts
- Summaries are written back into the Miniflux entry

## 🚀&nbsp;Installation

Install minigist using `pip`:

```bash
pip install minigist
```

Install minigist using `uv`:

```bash
uv tool install minigist
```

## 📄&nbsp;Usage

### Configuration

Create a configuration file at `~/.config/minigist/config.yaml`:

```yaml
miniflux:
  # Base URL of your Miniflux instance (required)
  url: "https://your-miniflux-instance.com"
  # Miniflux API key (required)
  api_key: "your-miniflux-api-key"
  # Request timeout in seconds (optional; default: 2)
  timeout_seconds: 2

llm:
  # API key for your LLM provider (required)
  api_key: "your-ai-service-api-key"
  # API base URL (optional; default: OpenRouter)
  base_url: "https://openrouter.ai/api/v1"
  # Model identifier to use (optional; default shown)
  model: "google/gemini-2.5-flash-lite"
  # Request timeout in seconds (optional; default: 60)
  timeout_seconds: 60
  # Max number of concurrent LLM requests (optional; default: 5)
  concurrency: 5

prompts:
  # Prompts define how summaries are produced.
  # Each prompt must have a unique id.
  - id: "default"
    prompt: "Generate an executive summary of the provided article."
  - id: "deep-dive"
    prompt: "Extract the nuanced arguments and counterpoints."

# Optional: when no targets are defined, this prompt is used for all unread entries.
# If omitted, the first prompt in the "prompts" list is used.
default_prompt_id: "default"

targets:
  # Targets map feeds or categories to prompts.
  # When targets are defined, ONLY these feeds/categories are processed.
  # Overlaps across targets are errors.
  - prompt_id: "default"
    feed_ids: [1, 2]
  - prompt_id: "deep-dive"
    category_ids: [5]
    # Prefer pure.md for this target (optional; default: false)
    use_pure: true

scraping:
  # Token for pure.md (optional; improves rate limits)
  pure_api_token: "optional-pure-md-token"
  # Always route matching URLs through pure.md
  pure_base_urls:
    - "https://text.npr.org/"
  # Request timeout for scraping in seconds (optional; default: 5)
  timeout_seconds: 5

fetch:
  # Max unread entries to fetch per feed (optional; default: 50)
  limit: 50

notifications:
  # Apprise notification URLs (optional)
  - "discord://webhook_id/webhook_token"
  - "telegram://bot_token/chat_id"
```

See [Apprise documentation](https://github.com/caronc/apprise) for all supported notification services.

### Run

Run minigist to process unread entries:

```bash
minigist run
```

Run in dry-run mode to see what would happen without making changes:

```bash
minigist run --dry-run
```

Increase logging verbosity:

```bash
minigist run --log-level DEBUG
```

Use a different configuration file:

```bash
minigist run --config-file /path/to/config.yaml
```
