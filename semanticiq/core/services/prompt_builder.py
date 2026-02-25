# services/prompt_builder.py
from .prompt_templates import PROMPT_TEMPLATES
import json, re
try:
    # If not configured during early MVP, we keep working without LLM.
    from .llm_client import LLMClient  # type: ignore
except Exception:
    LLMClient = None  # fallback: no LLM available

def build_model_from_prompt(user_prompt: str, template_id: str = None) -> dict:
    """
    Builds a model using an LLM prompt template.
    Uses LLMClient if available.
    """

    if not LLMClient:
        raise RuntimeError("LLMClient is not configured")

    # Load system prompt
    if template_id and template_id in PROMPT_TEMPLATES:
        system_prompt = PROMPT_TEMPLATES[template_id]
    else:
        system_prompt = (
            "You are an expert system designer. Convert the user description "
            "into an ontology-lite JSON model."
        )

    # Call your existing Mistral JSON-completion client
    client = LLMClient()
    result = client.complete_json(system_prompt, user_prompt)

    if result is None:
        raise RuntimeError("LLMClient returned no result")

    if not isinstance(result, dict):
        raise ValueError("LLMClient returned non-JSON content")

    return result

def fake_llm(prompt: str) -> dict:
    """
    Temporary stub until LLM integration is added.
    """
    return {
        "entities": [
            {
                "id": "Process",
                "label": "Process",
                "attributes": [
                    {"id": "name", "type": "string"},
                    {"id": "description", "type": "string"}
                ],
                "relationships": []
            }
        ],
        "sourcePrompt": prompt
    }
