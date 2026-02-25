# semanticiq/core/services/llm_client.py
import os
import json
from typing import Optional, Dict, Any, Type

try:
    # Official Mistral Python SDK
    from mistralai import Mistral
except Exception:  # pragma: no cover
    Mistral = None


class LLMClient:
    """
    Minimal abstraction for producing JSON outputs from prompts using Mistral.

    - JSON Mode: response_format={"type":"json_object"} enforces valid JSON output.
      (the SDK returns a stringified JSON object in the message content)
    - Pydantic Structured Outputs (optional): use client.chat.parse(...) to enforce a strict schema.
    """

    def __init__(self, model: str = None, temperature: float = 0.0, max_tokens: Optional[int] = None):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.provider = "mistral" if self.api_key else None
        self.model = model or "mistral-small-latest"
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize the SDK client if API key is present
        self.client = None
        if self.api_key and Mistral is not None:
            self.client = Mistral(api_key=self.api_key)

    def available(self) -> bool:
        """Return True if the Mistral client is ready."""
        return self.client is not None

    def _messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        """
        Build SDK messages. In JSON mode, always instruct the model explicitly to return ONLY JSON.
        """
        sys = (system_prompt or "").strip()
        # Strong JSON instruction helps stability in JSON Mode.
        sys_json_hint = (
            "Return ONLY a single valid JSON object that matches the requested format. "
            "Do not include explanations, Markdown, or additional text—just JSON."
        )
        messages = []
        if sys:
            messages.append({"role": "system", "content": f"{sys}\n\n{sys_json_hint}"})
        else:
            messages.append({"role": "system", "content": sys_json_hint})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def complete_json(self, system_prompt, user_prompt, schema=None):
        if not self.available():
            return None

        # Build messages
        messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
        ]

        try:
            resp = self.client.chat.complete(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}  # JSON mode still works
        )

            # Extract content
            choice = resp.choices[0]
            content = choice.message.content

            # Parse JSON
            return json.loads(content)

        except Exception as e:
            print("MISTRAL ERROR:", repr(e))
            return None

    def complete_pydantic(
        self,
        system_prompt: str,
        user_prompt: str,
        model_class: Optional[Type] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Stricter structured outputs via Pydantic:

        - Provide a Pydantic BaseModel subclass in `model_class`.
        - Uses `client.chat.parse(...)`, which enforces the schema and returns parsed content.

        Returns: dict parsed to the provided schema, or None.
        """
        if not self.available() or model_class is None:
            return None

        messages = [
            {"role": "system", "content": system_prompt or "Extract the requested fields."},
            {"role": "user", "content": user_prompt},
        ]
        try:
            parsed = self.client.chat.parse(
                model=self.model,
                messages=messages,
                response_format=model_class,       # Pydantic class
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            # Convert parsed Pydantic instance to dict (SDK returns an instance)
            # If SDK returns a dataclass-like object, ensure we coerce to dict.
            if hasattr(parsed, "dict"):
                return parsed.dict()
            if hasattr(parsed, "model_dump"):
                return parsed.model_dump()
            # Fallback: try to access `.data` or JSON string
            if hasattr(parsed, "data"):
                return parsed.data
            return None
        except Exception:
            return None
