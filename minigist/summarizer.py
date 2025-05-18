from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import LLMServiceConfig
from .logging import get_logger

logger = get_logger(__name__)


class Summarizer:
    def __init__(self, config: LLMServiceConfig):
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

    def generate_summary(self, article_text: str) -> str | None:
        if not article_text or not article_text.strip():
            logger.warning("Generate summary called with empty article text")
            return None

        logger.debug("Generating article summary", text_length=len(article_text))
        try:
            result = self.agent.run_sync(article_text)
        except Exception as e:
            logger.error("Unexpected error during LLM summarization", error=str(e))
            return None

        if not result or not result.output:
            logger.error("LLM service returned empty result or no output")
            return None

        summary = result.output

        if "minigist error" in summary.lower():
            logger.warning(
                "Model indicated error in summary output",
                summary_preview=summary[:100],
            )
            return None

        logger.debug("Successfully generated summary", summary_length=len(summary))
        return summary
