from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params.response_format_json_schema import ResponseFormatJSONSchema
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import LLMConfig
from .exceptions import LLMServiceError
from .logging import format_log_preview, get_logger

logger = get_logger(__name__)


class SummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary_markdown: str = Field(description="The generated summary in Markdown format.")
    error: bool = Field(
        description="Indicates if the input does not look like a full high-quality article but something else."
    )


class Summarizer:
    def __init__(self, config: LLMConfig):
        client_kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "timeout": config.timeout_seconds,
            "base_url": config.base_url,
        }

        self.client = AsyncOpenAI(**client_kwargs)
        self.model = config.model
        self.is_openrouter = "openrouter.ai" in config.base_url

    async def generate_summary(
        self,
        article_text: str,
        prompt: str,
        log_context: dict[str, object],
    ) -> str:
        if not article_text or not article_text.strip():
            logger.warning("Generate summary called with empty article text", **log_context)
            raise LLMServiceError("Cannot generate summary from empty or whitespace-only article text")

        logger.info("Generating article summary", **log_context, text_length=len(article_text))
        try:
            response_format: ResponseFormatJSONSchema = {
                "type": "json_schema",
                "json_schema": {
                    "name": SummaryOutput.__name__,
                    "description": "Structured summary output",
                    "strict": True,
                    "schema": SummaryOutput.model_json_schema(),
                },
            }

            messages: list[ChatCompletionMessageParam] = [
                cast(
                    ChatCompletionSystemMessageParam,
                    {"role": "system", "content": prompt},
                ),
                cast(
                    ChatCompletionUserMessageParam,
                    {"role": "user", "content": article_text},
                ),
            ]

            request_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "response_format": response_format,
            }

            # OpenRouter supports provider/plugins extras; OpenAI rejects unknown params.
            if self.is_openrouter:
                request_kwargs["extra_body"] = {
                    "provider": {"require_parameters": True},
                    "plugins": [{"id": "response-healing"}],
                }

            completion = await self.client.chat.completions.create(**request_kwargs)
        except Exception as e:
            logger.error("Unexpected error during LLM summarization", **log_context, error=str(e))
            raise LLMServiceError(f"LLM service error during summarization: {e}") from e

        content = completion.choices[0].message.content
        if not content:
            logger.error("LLM service returned empty structured output", **log_context)
            raise LLMServiceError("LLM service returned empty structured output")

        try:
            output = SummaryOutput.model_validate_json(content)
        except ValidationError as e:
            logger.error(
                "LLM structured output failed schema validation",
                **log_context,
                content_preview=format_log_preview(content),
            )
            raise LLMServiceError("LLM structured output failed schema validation") from e

        summary = output.summary_markdown
        logger.debug("Received summary output", **log_context, summary=summary)

        if output.error:
            logger.warning(
                "Model indicated error",
                **log_context,
                summary_preview=format_log_preview(summary),
            )
            raise LLMServiceError("LLM model indicated an error in its output")

        if not summary or not summary.strip():
            logger.error("LLM service returned empty summary markdown", **log_context)
            raise LLMServiceError("LLM service returned an empty summary")

        logger.debug("Successfully generated summary", **log_context, summary_length=len(summary))
        return summary
