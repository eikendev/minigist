from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import LLMServiceConfig
from .exceptions import LLMServiceError
from .logging import format_log_preview, get_logger

logger = get_logger(__name__)


class SummaryOutput(BaseModel):
    summary_markdown: str = Field(description="The generated summary in Markdown format.")
    error: bool = Field(
        description="Indicates if the input does not look like a full high-quality article but something else."
    )


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
            instructions=config.system_prompt,
            output_type=SummaryOutput,
        )

    def generate_summary(self, article_text: str) -> str:
        if not article_text or not article_text.strip():
            logger.warning("Generate summary called with empty article text")
            raise LLMServiceError("Cannot generate summary from empty or whitespace-only article text")

        logger.debug("Generating article summary", text_length=len(article_text))
        try:
            result = self.agent.run_sync(article_text)
        except Exception as e:
            logger.error("Unexpected error during LLM summarization", error=str(e))
            raise LLMServiceError(f"LLM service error during summarization: {e}") from e

        if not result or not result.output:
            logger.error("LLM service returned empty result or no structured output")
            raise LLMServiceError("LLM service returned empty result or no structured output")

        structured_output: SummaryOutput = result.output

        summary = structured_output.summary_markdown

        if structured_output.error:
            logger.warning(
                "Model indicated error",
                summary_preview=format_log_preview(summary),
            )
            raise LLMServiceError("LLM model indicated an error in its output")

        if not summary or not summary.strip():
            logger.error("LLM service returned empty summary markdown")
            raise LLMServiceError("LLM service returned an empty summary")

        logger.debug("Successfully generated summary", summary_length=len(summary))
        return summary
