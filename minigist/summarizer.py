import json

import trafilatura
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import AIServiceConfig
from .exceptions import AIServiceError, ArticleFetchError
from .logging import get_logger

logger = get_logger(__name__)


class Summarizer:
    def __init__(self, config: AIServiceConfig):
        logger.debug(
            "Using custom API configuration",
            has_api_key=bool(config.api_key),
            has_base_url=bool(config.base_url),
        )

        model = OpenAIModel(
            config.model,
            provider=OpenAIProvider(
                base_url=config.base_url,
                api_key=config.api_key,
            ),
        )
        self.agent = Agent(
            model,
            system_prompt=config.system_prompt,
        )

    def parse_html(self, html: str, url: str) -> str:
        logger.debug("Parsing article HTML", url=url)
        try:
            extracted = trafilatura.extract(
                html,
                output_format="json",
                with_metadata=True,
                include_comments=False,
            )
        except Exception as e:
            logger.error("Unexpected error extracting content", url=url, error=str(e))
            raise ArticleFetchError(
                f"Failed to extract article content from {url}"
            ) from e

        if not extracted:
            logger.error("No content extracted from article", url=url)
            raise ArticleFetchError(f"No content extracted from {url}")

        try:
            content = json.loads(extracted)
        except Exception as e:
            logger.error("Unexpected error parsing JSON", url=url, error=str(e))
            raise ArticleFetchError(
                f"Failed to parse extracted content for {url}"
            ) from e

        text = content.get("text")
        if not text:
            logger.error("No text content in extracted article", url=url)
            raise ArticleFetchError(f"No text content extracted from {url}")

        logger.debug("Successfully parsed text", url=url, length=len(text))
        return text

    def generate_summary(self, article_text: str) -> str:
        logger.debug("Generating article summary", length=len(article_text))
        try:
            result = self.agent.run_sync(article_text)
        except Exception as e:
            logger.error("Unexpected error during summarization", error=str(e))
            raise AIServiceError("Unexpected error during summarization") from e

        if not result or not result.output:
            logger.error("AI service returned an empty result")
            raise AIServiceError("AI service returned an empty result")

        summary = result.output

        if "minigist error" in summary.lower():
            logger.error("Model indicated error in summary", summary=summary)
            raise AIServiceError("AI service returned an error in summary")

        logger.debug("Successfully generated summary", length=len(summary))
        return summary
