FROM python:3.13-slim

ARG VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION

# Ensure that all commands within the Dockerfile compile bytecode.
ENV UV_COMPILE_BYTECODE=1

# Silence warnings about not being able to use hard links.
ENV UV_LINK_MODE=copy

# Disable interactive prompts during package installs.
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Place executables in the environment at the front of the path.
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install gnupg and curl for adding Google Chrome repository.
RUN apt-get update && apt-get install -y --no-install-recommends gnupg curl \
	&& rm -rf /var/lib/apt/lists/*

# Install Xvfb, required libraries, and Google Chrome Stable.
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
	&& echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
		> /etc/apt/sources.list.d/google-chrome.list \
	&& apt-get update && apt-get install -y --no-install-recommends \
		xvfb \
		libglib2.0-0 \
		libnss3 \
		libgtk-3-0 \
		google-chrome-stable \
		unzip \
	&& rm -rf /var/lib/apt/lists/* \
	&& rm /etc/apt/sources.list.d/google-chrome.list

# Install dependencies only.
RUN --mount=type=cache,target=/root/.cache/uv \
	--mount=type=bind,source=uv.lock,target=uv.lock \
	--mount=type=bind,source=pyproject.toml,target=pyproject.toml \
	uv sync --locked --no-install-project

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

# Use SeleniumBase CLI to fetch the stable ChromeDriver.
RUN uv run sbase get chromedriver stable

ENTRYPOINT ["minigist"]
