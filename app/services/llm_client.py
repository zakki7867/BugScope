"""Thin LLM client with structured output validation and 1-retry fallback.

Uses httpx for HTTP requests against an OpenAI-compatible endpoint (e.g. Gemini, OpenAI, or local vLLM).
Model name and API key are read dynamically from Settings.
All LLM responses are parsed strictly into Pydantic v2 models, retrying once on failure.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Approximate pricing per 1M tokens (Gemini 2.0 Flash baseline)
PRICE_INPUT_PER_1M = 0.10
PRICE_OUTPUT_PER_1M = 0.40


class LLMClientError(Exception):
    """Raised when LLM communication or structured validation fails."""
    pass


class LLMUsageTrace(BaseModel):
    """Execution telemetry for an LLM call."""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: float = 0.0
    cost_usd: float = 0.0


class LLMClient:
    """Thin wrapper around LLM provider for structured JSON responses."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.api_key
        self.model = model or settings.model
        self.api_base = (api_base or settings.api_base).rstrip("/")
        self.client = http_client or httpx.Client(timeout=60.0)

    def _calculate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Calculate approximate cost in USD."""
        cost = (tokens_in / 1_000_000.0 * PRICE_INPUT_PER_1M) + (
            tokens_out / 1_000_000.0 * PRICE_OUTPUT_PER_1M
        )
        return round(cost, 6)

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str = "",
        max_retries: int = 1,
    ) -> Tuple[T, LLMUsageTrace]:
        """Generate structured output adhering to response_model, retrying once on failure.

        Args:
            prompt: User prompt content.
            response_model: Pydantic v2 class to validate against.
            system_instruction: Instructions for system message.
            max_retries: Maximum validation retries (default 1).

        Returns:
            Tuple of (validated Pydantic model instance, LLMUsageTrace).
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        augmented_system = (
            f"{system_instruction}\n\n"
            "CRITICAL: You MUST respond ONLY with valid JSON matching the following schema. "
            "Do not include markdown code fences (```json), markdown commentary, or introductory text.\n"
            f"Schema:\n{schema_json}"
        )

        messages = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": prompt},
        ]

        attempt = 0
        total_tokens_in = 0
        total_tokens_out = 0
        total_duration = 0.0
        last_error = ""

        while attempt <= max_retries:
            start_t = time.time()
            attempt += 1

            try:
                # If no API key is provided, handle gracefully or raise clear error
                if not self.api_key:
                    raise LLMClientError(
                        "BUGSCOPE_API_KEY is not set in environment or .env file."
                    )

                url = f"{self.api_base}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                }

                resp = self.client.post(url, headers=headers, json=payload)
                elapsed_ms = round((time.time() - start_t) * 1000, 2)
                total_duration += elapsed_ms

                if resp.status_code != 200:
                    raise LLMClientError(
                        f"LLM API request failed with status {resp.status_code}: {resp.text}"
                    )

                data = resp.json()
                usage = data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", len(prompt) // 4)
                tokens_out = usage.get("completion_tokens", len(resp.text) // 4)
                total_tokens_in += tokens_in
                total_tokens_out += tokens_out

                content = data["choices"][0]["message"]["content"].strip()
                # Strip potential markdown fences if returned
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                parsed = response_model.model_validate_json(content)
                cost = self._calculate_cost(total_tokens_in, total_tokens_out)
                trace = LLMUsageTrace(
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    duration_ms=total_duration,
                    cost_usd=cost,
                )
                return parsed, trace

            except (ValidationError, json.JSONDecodeError, KeyError) as val_err:
                last_error = str(val_err)
                logger.warning(
                    "Structured validation failed on attempt %d: %s", attempt, last_error
                )
                if attempt <= max_retries:
                    # Append feedback message to retry once
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Your previous response failed validation: {last_error}. "
                                "Please fix the JSON and adhere strictly to the schema."
                            ),
                        }
                    )
            except Exception as e:
                # Direct LLM / network error
                raise LLMClientError(f"LLM request error: {str(e)}") from e

        raise LLMClientError(
            f"Failed to produce valid structured output after {max_retries + 1} attempts. Last error: {last_error}"
        )
