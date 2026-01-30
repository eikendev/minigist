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

## 🤘&nbsp;Features

- **Automatic summarization** of unread Miniflux entries
- **Configurable filters** to target specific feeds
- **Notification support** via Apprise for various messaging services
- **Dry-run mode** to preview changes without modifying entries
- **Structured logging** for better debugging and monitoring

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
  url: "https://your-miniflux-instance.com"
  api_key: "your-miniflux-api-key"
  timeout_seconds: 2  # Default

llm:
  api_key: "your-ai-service-api-key"
  base_url: "https://openrouter.ai/api/v1"   # Default
  model: "google/gemini-2.0-flash-lite-001"  # Default
  timeout_seconds: 60                        # Default
  concurrency: 5                             # Default

prompts:
  - id: "default"
    prompt: "Generate an executive summary of the provided article."
  - id: "deep-dive"
    prompt: "Extract the nuanced arguments and counterpoints."

# Optional: when no targets are defined, this prompt is used for all unread entries
# If omitted, the first prompt in the list is used.
default_prompt_id: "default"

targets:
  # When targets are defined, only these feeds/categories are processed; overlaps across targets are errors.
  - prompt_id: "default"
    feed_ids: [1, 2]
  - prompt_id: "deep-dive"
    category_ids: [5]
    use_pure: true  # Prefer pure.md for this target

scraping:
  pure_api_token: "optional-pure-md-token"
  # Always route matching URLs through pure.md.
  pure_base_urls:
    - "https://text.npr.org/"
  timeout_seconds: 5  # Default

fetch:
  limit: 50     # Default

notifications:
  urls:                # Apprise notification URLs (optional)
    - "discord://webhook_id/webhook_token"
    - "telegram://bot_token/chat_id"
```

See [Apprise documentation](https://github.com/caronc/apprise) for all supported notification services.

### Basic Commands

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
