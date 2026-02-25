from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from typing import Tuple
from .interpreter_agent import interpret


@dataclass
class ConversationState:
    entity: Optional[str] = None
    intent: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    awaiting_field: Optional[str] = None
    last_system_message: Optional[str] = None
    done: bool = True

def get_entity_schema(model_json: Dict[str, Any], entity: str) -> Dict[str, Any]:
    for e in model_json.get("entities", []):
        if e.get("id") == entity:
            return {attr["id"]: attr for attr in e.get("attributes", [])}
    return {}

def compute_missing_fields(schema: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
    missing = []
    for field, meta in schema.items():
        # Default: fields are required unless explicitly optional
        is_required = meta.get("required", True)

        if is_required and not data.get(field):
            missing.append(field)

    return missing

def question_for_field(field_name: str, schema: Dict[str, Any]) -> str:
    meta = schema.get(field_name, {})
    label = meta.get("label", field_name)
    field_type = meta.get("type", "string")

    if field_type == "number":
        return f"What {label} should I use?"
    if field_type == "date":
        return f"What is the {label} (date)?"
    if field_type == "boolean":
        return f"Should {label} be true or false?"
    if meta.get("enum"):
        options = ", ".join(meta["enum"])
        return f"What {label} should I use? Options: {options}"
    return f"I need the {label}. Could you tell me that?"

class ConversationManager:
    def __init__(self, model_json: Dict[str, Any]):
        self.model_json = model_json

    def start_or_continue(
        self,
        state: ConversationState,
        message: str
    ) -> tuple[ConversationState, str]:
        """
        FIXED VERSION:
        - ConversationManager no longer calls interpret()
        - It ONLY continues an already-started workflow
        - The /chat endpoint is the ONLY place that decides intent
        """       

        # ---------------------------------------------------------
        # 1) If we're awaiting a specific field → fill it
        # ---------------------------------------------------------
        if state.awaiting_field and state.entity:
            return self._handle_field_answer(state, message)

        # ---------------------------------------------------------
        # 2) If no workflow is active → this is NOT an action intent
        # ---------------------------------------------------------
        if not state.entity or not state.intent:
            reply = (
                "I’m not sure what you want to do. "
                "Are you asking about an entity like Invoice or Purchase Order?"
            )
            state.last_system_message = reply
            return state, reply

        # ---------------------------------------------------------
        # 3) Ensure schema fields exist
        # ---------------------------------------------------------
        schema = get_entity_schema(self.model_json, state.entity)
        for f in schema.keys():
            state.data.setdefault(f, None)

        # ---------------------------------------------------------
        # 4) Compute missing fields
        # ---------------------------------------------------------
        state.missing_fields = compute_missing_fields(schema, state.data)

        # ---------------------------------------------------------
        # 5) If no missing fields → workflow is complete
        # ---------------------------------------------------------
        if not state.missing_fields:
            state.done = True
            reply = self._confirm_and_create(state)
            state.last_system_message = reply
            return state, reply

        # ---------------------------------------------------------
        # 6) Ask for the next missing field
        # ---------------------------------------------------------
        next_field = state.missing_fields[0]
        state.awaiting_field = next_field
        question = question_for_field(next_field, schema)
        state.last_system_message = question
        return state, question

    # ---------------- internal helpers ----------------

    def _handle_field_answer(
        self,
        state: ConversationState,
        message: str
    ) -> tuple[ConversationState, str]:

        field_name = state.awaiting_field
        schema = get_entity_schema(self.model_json, state.entity)
        meta = schema.get(field_name, {})

        # Basic parsing
        value = self._coerce_value(message, meta)

        state.data[field_name] = value
        state.awaiting_field = None

        # Recompute missing fields
        state.missing_fields = compute_missing_fields(schema, state.data)

        if state.missing_fields:
            next_field = state.missing_fields[0]
            state.awaiting_field = next_field
            question = question_for_field(next_field, schema)
            state.last_system_message = question
            return state, question

        # All fields present → create workflow
        state.done = True
        reply = self._confirm_and_create(state)
        state.last_system_message = reply
        return state, reply

    def _coerce_value(self, message: str, meta: Dict[str, Any]):
        t = meta.get("type", "string")
        if t == "number":
            try:
                return float(message)
            except ValueError:
                return None
        if t == "boolean":
            m = message.strip().lower()
            if m in ("yes", "true", "y", "1"):
                return True
            if m in ("no", "false", "n", "0"):
                return False
            return None
        return message.strip()

    def _confirm_and_create(self, state: ConversationState) -> str:
        return f"Got it. I’ll create a {state.entity} with: {state.data}"