from typing import Optional

from newspaper import Article, ArticleException  # type: ignore
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

    def fetch_and_parse_article(self, url: str) -> Optional[str]:
        logger.debug("Fetching article content", url=url)

        try:
            article = Article(url)
            article.download()
            article.parse()
        except ArticleException as e:
            logger.error("Newspaper3k failed to process article", url=url, error=str(e))
            raise ArticleFetchError(f"Failed to fetch/parse article {url}") from e
        except Exception as e:
            logger.error(
                "Unexpected error fetching article",
                url=url,
                error=str(e),
            )
            raise ArticleFetchError(f"Unexpected error fetching article {url}") from e

        text = article.text

        if not text:
            logger.warning("No text content extracted from article", url=url)
            return None

        logger.debug("Successfully extracted text", url=url, length=len(text))
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
        logger.debug("Successfully generated summary", length=len(summary))

        return summary
