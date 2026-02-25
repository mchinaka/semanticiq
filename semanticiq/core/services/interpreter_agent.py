# -*- coding: utf-8 -*-
"""
Interpreter agent: NL -> intent dict.

Hardened to:
- Accept dict | list | str model_json.
- Normalize/defensively access entities/workflows.
- Lower-case synonym matching.
- Be resilient if LLM is absent or returns non-JSON.
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, Optional, Tuple, List, Callable, TypedDict
from .validator import ValidationError
from .extractors import get_type_extractor, get_tag_extractor, extract_entity_from_text


try:
    # If not configured during early MVP, we keep working without LLM.
    from .llm_client import LLMClient  # type: ignore
except Exception:
    LLMClient = None  # fallback: no LLM available


# ---- Synonyms (lowercase to match lowercased text) --------------------------

CREATE_SYNONYMS  = ["create", "new", "open", "raise", "make"]
SUBMIT_SYNONYMS  = ["submit", "send", "file", "forward"]
APPROVE_SYNONYMS = ["approve", "ok", "authorize", "sign off", "sign-off"]
CLOSE_SYNONYMS   = ["close", "complete", "finish"]

CURRENCY_MAP = {
    "€": "EUR", "eur": "EUR", "euro": "EUR",
    "$": "USD", "usd": "USD", "dollar": "USD",
    "£": "GBP", "gbp": "GBP", "pound": "GBP"
}

QUESTION_WORDS = ("what", "how", "why", "when", "who", "explain", "describe", "tell me")
ACTION_WORDS = ("create", "update", "approve", "submit", "start", "open")


# ---- Intent type ------------------------------------------------------------

class IntentDict(TypedDict):
    intent: str
    entity: Optional[str]
    event: Optional[str]
    data: Dict[str, Any]
    confidence: float


# ---- Normalization helpers --------------------------------------------------

def _normalize_model(model_json: Any) -> Dict[str, Any]:
    """
    Accepts dict | list | str -> returns a best-effort model dict.
    Prefers an item that contains 'entities'.
    """
    if isinstance(model_json, str):
        try:
            model_json = json.loads(model_json)
        except Exception:
            return {}

    if isinstance(model_json, list):
        for item in model_json:
            if isinstance(item, dict) and "entities" in item:
                return item
        for item in model_json:
            if isinstance(item, dict):
                return item
        return {}

    if isinstance(model_json, dict):
        return model_json

    return {}


def _entities(model: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Normalize model['entities'] (list or dict) into a dict keyed by id/name.
    """
    entities = model.get("entities") or {}
    if isinstance(entities, dict):
        return entities

    entity_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(entities, list):
        for e in entities:
            if not isinstance(e, dict):
                continue
            eid = e.get("id") or e.get("name")
            if not eid:
                continue
            entity_map[str(eid)] = e
    return entity_map


def _workflow_items(model: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Returns list of (entity_or_name, workflow_spec) pairs
    whether 'workflows' is a dict or a list.
    """
    wfs = model.get("workflows") or {}
    items: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(wfs, dict):
        for key, wf in wfs.items():
            if isinstance(wf, dict):
                items.append((str(key), wf))
        return items
    if isinstance(wfs, list):
        for i, wf in enumerate(wfs):
            if not isinstance(wf, dict):
                continue
            name = wf.get("entity") or wf.get("name") or f"workflow_{i}"
            items.append((str(name), wf))
        return items
    return items


# ---- Basic heuristics: entity, action, event --------------------------------

def _guess_entity(model: Dict[str, Any], text: str) -> Optional[str]:
    entity_map = _entities(model)
    entities = list(entity_map.keys())
    if not entities:
        return None

    t = text.lower()
    for e in entities:
        if e.lower() in t:
            return e

    if "po" in t and "PurchaseOrder" in entities:
        return "PurchaseOrder"

    return entities[0]  # default fallback


def _guess_event(text: str) -> Optional[str]:
    t = text.lower()
    if any(w in t for w in SUBMIT_SYNONYMS):
        return "submit"
    if any(w in t for w in APPROVE_SYNONYMS):
        return "approve"
    if any(w in t for w in CLOSE_SYNONYMS):
        return "close"
    return None


def _guess_action(text: str) -> str:
    t = text.lower()
    if any(w in t for w in CREATE_SYNONYMS):
        return "create"
    ev = _guess_event(text)
    if ev:
        return "signal"
    return "create"


def heuristic_classify(message: str, model_json: dict) -> dict | None:
    text = message.lower().strip()

    # Knowledge heuristic
    if any(text.startswith(w) for w in QUESTION_WORDS) or text.endswith("?"):
        entity = extract_entity_from_text(model_json, text)
        return {"intent_type": "knowledge", "entity": entity}

    # Action heuristic
    if any(w in text for w in ACTION_WORDS):
        return {"intent_type": "action"}

    # Entity detection (supports list or dict)
    raw_entities = model_json.get("entities", {})

    # Normalize to dict: {entity_id: entity_def}
    if isinstance(raw_entities, list):
        entities = {e.get("id"): e for e in raw_entities}
    else:
        entities = raw_entities

    for ename in entities.keys():
        if ename and ename.lower() in text:
            return {"intent_type": "knowledge", "entity": ename}

        spaced = re.sub(r"([A-Z])", r" \1", ename).strip().lower()
        if spaced in text:
            return {"intent_type": "knowledge", "entity": ename}

    return None


# ---- Type-driven extractors -------------------------------------------------

Extractor = Callable[[str], Optional[Any]]


def extract_number(text: str) -> Optional[float]:
    m = re.search(r'\b([0-9][0-9,.\s]{1,})\b', text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "").strip())
    except Exception:
        return None


def extract_currency(text: str) -> Optional[str]:
    t = text.lower()
    for k, v in CURRENCY_MAP.items():
        if k.lower() in t:
            return v
    return None


def extract_boolean(text: str) -> Optional[bool]:
    t = text.lower()
    if any(w in t for w in ["yes", "true", "y", "ok", "sure"]):
        return True
    if any(w in t for w in ["no", "false", "n", "not really"]):
        return False
    return None


def extract_free_text(text: str) -> Optional[str]:
    return None


def extract_date(text: str) -> Optional[str]:
    # Placeholder: plug in a real date parser if you want.
    # For now, return None to avoid false positives.
    return None


TYPE_EXTRACTORS: Dict[str, Extractor] = {
    "number": extract_number,
    "currency": extract_currency,
    "boolean": extract_boolean,
    "string": extract_free_text,
    "text": extract_free_text,
    "date": extract_date,
}


def extract_attributes_for_entity(
    model: Dict[str, Any],
    entity: Optional[str],
    message: str
) -> Dict[str, Any]:
    """
    Model-driven, type-driven, tag-aware attribute extraction.
    Supports list-shaped attributes and tag-based overrides.
    """
    if not entity:
        return {}

    entity_map = _entities(model)
    spec = entity_map.get(entity)
    if not isinstance(spec, dict):
        return {}

    raw_attrs = spec.get("attributes") or {}
    attrs_dict: Dict[str, Any] = {}

    # Normalize attributes: list → dict
    if isinstance(raw_attrs, list):
        for attr in raw_attrs:
            if not isinstance(attr, dict):
                continue
            attr_id = attr.get("id") or attr.get("name")
            if not attr_id:
                continue
            attrs_dict[str(attr_id)] = attr
    elif isinstance(raw_attrs, dict):
        attrs_dict = raw_attrs

    data: Dict[str, Any] = {}

    for attr_name, attr_spec in attrs_dict.items():
        if not isinstance(attr_spec, dict):
            attr_type = str(attr_spec)
            tags = []
        else:
            attr_type = attr_spec.get("type", "string")
            tags = attr_spec.get("tags") or []

        # 1) Tag-based override (highest priority)
        extractor = None
        for tag in tags:
            tag_name = tag.split(":", 1)[0]  # e.g. "foreignKey:Supplier" → "foreignKey"
            extractor = get_tag_extractor(tag_name)
            if extractor:
                break

        # 2) Type-based extractor (fallback)
        if extractor is None:
            extractor = get_type_extractor(attr_type)

        if not extractor:
            continue

        value = extractor(message)
        if value is not None:
            data[attr_name] = value

    return data


# ---- Prompt building for LLM -----------------------------------------------

def build_system_prompt(model_json: Any) -> str:
    model = _normalize_model(model_json)
    entity_map = _entities(model)
    parts = [
        "You convert user requests to a strict JSON intent based on the ontology.",
        "Use only entities, attributes, and workflow events defined in the model.",
    ]

    for entity, spec in entity_map.items():
        attrs_dict = (spec.get("attributes") or {}) if isinstance(spec, dict) else {}
        attrs = ", ".join(attrs_dict.keys())
        parts.append(f"- Entity {entity} attributes: {attrs}")

    for entity_or_name, wf in _workflow_items(model):
        transitions = wf.get("transitions") or []
        events = set()
        for t in transitions:
            if not isinstance(t, dict):
                continue
            ev = t.get("event") or t.get("on")
            if ev:
                events.add(ev)
        ev_s = ", ".join(sorted(events))
        parts.append(f"- Workflow {entity_or_name} events: {ev_s}")

    parts.append(
        """Return JSON like:
{
 "intent": "Create<EntityName>" | "Signal<EntityName>",
 "entity": "<EntityName or null>",
 "event": "submit|approve|close|null",
 "data": { ... attributes ... },
 "confidence": 0..1
}"""
    )
    return "\n".join(parts)

#---- Model-driven vocab building ------------------------------------------------
def build_entity_vocab(model_json):
    vocab = []

    # Base entity definitions
    for e in model_json.get("entities", []):
        vocab.append({
            "id": e["id"],
            "label": e.get("label", e["id"]),
            "synonyms": [],
            "description": ""
        })

    # Enrich with glossary synonyms + descriptions
    glossary = model_json.get("glossary", [])
    for g in glossary:
        for v in vocab:
            if v["id"] == g["id"]:
                v["synonyms"] = g.get("synonyms", [])
                v["description"] = g.get("description", "")
                break

    return vocab


# ---- Heuristic interpreter --------------------------------------------------

def interpret_heuristic(model_json, message):
    msg = message.lower().strip()
    print("INTERPRET_HEURISTIC:", message)

    # If it's a question → DO NOT infer action
    QUESTION_WORDS = ("what", "how", "why", "when", "who", "explain", "describe", "tell me")
    if any(msg.startswith(w) for w in QUESTION_WORDS) or msg.endswith("?"):
        return {"entity": None, "intent": None, "confidence": 0.0}

    vocab = build_entity_vocab(model_json)

    # 1. Exact match on label or synonyms
    for entry in vocab:
        if entry["label"].lower() in msg:
            return {"entity": entry["id"], "intent": f"Create{entry['id']}", "confidence": 0.9}

        for syn in entry["synonyms"]:
            if syn.lower() in msg:
                return {"entity": entry["id"], "intent": f"Create{entry['id']}", "confidence": 0.9}

    # 2. Fuzzy match on entity ID
    for entry in vocab:
        if entry["id"].lower() in msg:
            return {"entity": entry["id"], "intent": f"Create{entry['id']}", "confidence": 0.7}

    # 3. Fallback
    return {"entity": None, "intent": None, "confidence": 0.2}

# ---- LLM refinement + normalization ----------------------------------------

def normalize_intent(candidate: IntentDict, refined: Dict[str, Any]) -> IntentDict:
    intent = refined.get("intent") or candidate["intent"]
    entity_out = refined.get("entity") or candidate["entity"]
    event_out = refined.get("event") if refined.get("event") is not None else candidate["event"]
    data_out = refined.get("data") or candidate["data"]
    conf = refined.get("confidence")
    if not isinstance(conf, (int, float)):
        conf = candidate["confidence"]

    if not isinstance(data_out, dict):
        data_out = candidate["data"]

    return IntentDict(
        intent=str(intent),
        entity=str(entity_out) if entity_out is not None else None,
        event=str(event_out) if event_out is not None else None,
        data=data_out,
        confidence=float(conf),
    )

def build_refinement_prompt(model: Dict[str, Any], entity: str, message: str, partial_data: Dict[str, Any]) -> str:
    entity_map = _entities(model)
    spec = entity_map.get(entity, {})
    attrs = spec.get("attributes", [])

    # Normalize attributes list
    if isinstance(attrs, dict):
        attrs_list = [
            {"id": name, **(attrs[name] if isinstance(attrs[name], dict) else {"type": str(attrs[name])})}
            for name in attrs
        ]
    else:
        attrs_list = [a for a in attrs if isinstance(a, dict)]

    schema_lines = []
    for attr in attrs_list:
        aid = attr.get("id")
        atype = attr.get("type", "string")
        required = attr.get("required", False)
        enum = attr.get("enum")
        default = attr.get("default")

        line = {
            "id": aid,
            "type": atype,
            "required": required,
            "enum": enum,
            "default": default,
        }
        schema_lines.append(line)

    prompt = f"""
You are a strict JSON API that maps a natural language request into a structured payload
for the entity "{entity}" in a workflow system.

User message:
\"\"\"{message}\"\"\"

Entity schema (attributes):
{schema_lines}

Partial extraction (heuristics):
{partial_data}

Your task:
- Use the schema to fill in missing attributes.
- Correct any obviously wrong values.
- Respect types, enums, required flags, and defaults.
- If a required field cannot be inferred, set it to null.
- Do NOT invent IDs or foreign keys unless clearly stated.
- Return ONLY a JSON object with attribute names as keys.

Output format:
{{ "attributeName": value, ... }}
"""
    return prompt.strip()


def call_llm_and_parse_json(prompt: str) -> Dict[str, Any]:
    """
    Sends a prompt to the LLM and returns a parsed JSON object.
    - Uses LLMClient.complete_json correctly
    - Handles dict output directly
    - Falls back to JSON extraction if needed
    """
    try:
        llm = LLMClient()
        
        if not llm.available():            
            return {}

        # Correct call signature
        raw = llm.complete_json(system_prompt="", user_prompt=prompt)

        if raw is None:
            return {}

        # If the LLM already returned a dict, just return it
        if isinstance(raw, dict):            
            return raw

        # If it returned a string (rare), continue with parsing
        if isinstance(raw, str):
            text = raw
        else:
            # Unexpected type
            return {}        

        # Try direct JSON parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # Extract JSON substring
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        # Auto-repair
        repaired = (
            text.replace("\n", " ")
                .replace("\t", " ")
                .replace("“", '"')
                .replace("”", '"')
                .replace("'", '"')
        )

        match = re.search(r"\{[\s\S]*\}", repaired)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        return {}

    except Exception as e:        
        return {}

def refine_with_llm(model_json, message, heuristic):
    llm = LLMClient()
    if not llm.available():
        print("LLM unavailable")
        return heuristic

    entity = heuristic.get("entity")

    # FIX: extract schema from attributes
    entities = model_json.get("entities", [])
    entity_obj = next((e for e in entities if e.get("id") == entity), None)

    if entity_obj:
        schema = {
            attr["id"]: {
                "type": attr.get("type"),
                "required": attr.get("required", False),
                "enum": attr.get("enum"),
                "default": attr.get("default")
            }
            for attr in entity_obj.get("attributes", [])
        }
    else:
        schema = {}

    system_prompt = """
- intent
- entity
- data (an object containing all entity fields)

Always use the key "data" to hold the entity fields.
If a field cannot be inferred, set it to null.
Never use "fields", "attributes", or any other key.
"""

    user_prompt = f"""
User message:
{message}

Heuristic extraction:
{json.dumps(heuristic, indent=2)}

Entity: {entity}

Fields schema:
{json.dumps(schema, indent=2)}
"""
    raw = llm.complete_json(system_prompt, user_prompt, schema=schema)   

    return raw or heuristic

#---- generic LLM fallback classifier-------------------------------------------------------
def llm_classify_intent(model_json, message):
    """
    Extended LLM classifier:
    - Detects action / knowledge / other
    - Extracts entity (LLM + heuristic fallback)
    - Suggests action intent when applicable
    """

    # -------------------------
    # Strong heuristic override:
    # Questions MUST be knowledge
    # -------------------------
    lower = message.lower().strip()
    QUESTION_WORDS = ("what", "how", "why", "when", "who", "explain", "describe", "tell me")

    def extract_entity_from_text(text: str) -> str | None:
        raw_entities = model_json.get("entities", {})
        if isinstance(raw_entities, list):
            entities = {e.get("id"): e for e in raw_entities}
        else:
            entities = raw_entities

        t = text.lower()
        for ename in entities.keys():
            if not ename:
                continue

            if ename.lower() in t:
                return ename

            spaced = re.sub(r"([A-Z])", r" \1", ename).strip().lower()
            if spaced in t:
                return ename

        return None

    # If it's a question → force knowledge intent
    if any(lower.startswith(w) for w in QUESTION_WORDS) or lower.endswith("?"):
        extracted = extract_entity_from_text(message)
        return {
            "intent_type": "knowledge",
            "entity": extracted,
            "intent": None
        }

    # -------------------------
    # LLM classification (only for non-questions)
    # -------------------------
    llm = LLMClient()
    if not llm.available():
        return None

    raw_entities = model_json.get("entities", {})
    if isinstance(raw_entities, list):
        entities = {e.get("id"): e for e in raw_entities}
    else:
        entities = raw_entities

    vocab = build_entity_vocab(entities)

    system_prompt = """
You are an intent classifier for a workflow automation system.

Your job is to classify the user's message into one of:
- action: user wants to create/update/approve a workflow
- knowledge: user is asking about an entity, fields, workflow, or model
- other: anything else

You must also extract the entity if mentioned.

Return ONLY a JSON object with:
{
  "intent_type": "action" | "knowledge" | "other",
  "entity": "<EntityName or null>",
  "intent": "<ActionIntent or null>"
}

Rules:
- Do NOT invent entities.
- Do NOT invent fields.
- Use the known entities list.
- If the user wants to create something, intent must be Create<EntityName>.
- If the user is asking a question, intent_type must be "knowledge".
- If unclear, choose "other".
"""

    user_prompt = f"""
User message:
{message}

Known entities:
{json.dumps(vocab, indent=2)}
"""

    result = llm.complete_json(system_prompt, user_prompt)

    if not isinstance(result, dict):
        result = {"intent_type": "other", "entity": None, "intent": None}

    result.setdefault("intent_type", "other")
    result.setdefault("entity", None)
    result.setdefault("intent", None)

    # Heuristic fallback entity extraction
    if not result.get("entity"):
        extracted = extract_entity_from_text(message)
        if extracted:
            result["entity"] = extracted

    # Auto-fill action intent
    if result["intent_type"] == "action" and result["entity"] and not result["intent"]:
        result["intent"] = f"Create{result['entity']}"

    return result

#---hybrid classification -------------------------------------------------------

def hybrid_classify_intent(message: str, model_json: dict) -> dict:
    # Normalize entities
    raw_entities = model_json.get("entities", {})
    if isinstance(raw_entities, list):
        entities = {e.get("id"): e for e in raw_entities}
    else:
        entities = raw_entities

    # 1. Heuristic
    h = heuristic_classify(message, model_json)
    if h:
        return h

    # 2. LLM fallback
    return llm_classify_intent(model_json, message)

# ---- Public entrypoint ------------------------------------------------------

def interpret(model_json: Dict[str, Any], message: str, use_llm: bool = True) -> Dict[str, Any]:
    print(">>> INTERPRET CALLED WITH:", message)
    """
    Full hybrid interpreter:
    1) Hybrid classification (heuristics + LLM)
    2) If knowledge → return early
    3) If action → run your existing heuristic + refinement pipeline
    4) If other → return early for fallback LLM answering
    """

    # ---------------------------------------------------------
    # 1) Hybrid classification (heuristics + LLM)
    # ---------------------------------------------------------
    classification = hybrid_classify_intent(message, model_json)
    intent_type = classification.get("intent_type")
    classified_entity = classification.get("entity")
    print("HYBRID CLASSIFICATION:", classification)

    # ---------------------------------------------------------
    # 2) Knowledge intent → handled by knowledge answerer
    # ---------------------------------------------------------
    if intent_type == "knowledge":
        return {
            "intent_type": "knowledge",
            "intent": "AskAboutModel",
            "entity": classified_entity,
            "data": {},
            "confidence": 1.0
        }

    # ---------------------------------------------------------
    # 3) Other intent → handled by fallback LLM answerer
    # ---------------------------------------------------------
    if intent_type == "other":
        return {
            "intent_type": "other",
            "intent": None,
            "entity": classified_entity,
            "data": {},
            "confidence": 0.5
        }

    # ---------------------------------------------------------
    # 4) Action intent → run your existing pipeline
    # ---------------------------------------------------------

    # 4.1 Heuristic interpretation
    candidate = interpret_heuristic(model_json, message)

    # 4.2 If heuristic uncertain → LLM classification refinement
    if candidate.get("confidence", 0) < 0.8:
        llm_guess = llm_classify_intent(model_json, message)
        if llm_guess:
            candidate.update(llm_guess)
            candidate["confidence"] = 0.9

    # If still no entity → return early
    if not candidate.get("entity"):
        candidate["intent_type"] = "action"
        candidate["validation_errors"] = ["Unable to determine entity"]
        return candidate

    # 4.3 If LLM disabled → validate heuristic result only
    if not use_llm or LLMClient is None:
        candidate["intent_type"] = "action"
        try:
            validate_entity_payload(
                model_json,
                candidate.get("entity"),
                candidate.get("data") or {}
            )
        except ValidationError as ve:
            candidate["validation_errors"] = ve.errors
        return candidate

    # 4.4 LLM refinement (schema-driven)
    refined = refine_with_llm(
        model_json=model_json,
        message=message,
        heuristic=candidate
    )

    refined["intent_type"] = "action"

    # Normalize LLM output
    if "fields" in refined and "data" not in refined:
        refined["data"] = refined.pop("fields")

    if "data" not in refined or refined["data"] is None:
        refined["data"] = {}

    # 4.5 Ensure all schema fields exist
    entity = refined.get("entity")
    schema = {}

    for e in model_json.get("entities", []):
        if e.get("id") == entity:
            schema = {attr["id"]: attr for attr in e.get("attributes", [])}
            break

    for field in schema.keys():
        refined["data"].setdefault(field, None)

    # 4.6 Validate refined payload
    try:
        validate_entity_payload(
            model_json,
            refined.get("entity"),
            refined.get("data") or {}
        )
    except ValidationError as ve:
        refined["validation_errors"] = ve.errors

    return refined


def validate_entity_payload(model_json, entity_name, data):
    """
    Validates the payload for a given entity.
    - Required fields must exist in the payload
    - Required fields may be null (LLM placeholder)
    - Type checks only apply when value is not null
    """
    errors = []

    # Find entity definition
    entities = model_json.get("entities", [])
    entity = next((e for e in entities if e.get("id") == entity_name), None)

    if not entity:
        errors.append(f"Unknown entity: {entity_name}")
        raise ValidationError(errors)

    # Build schema from attributes
    attributes = entity.get("attributes", [])

    for attr in attributes:
        field = attr["id"]
        required = attr.get("required", False)
        expected_type = attr.get("type")

        # 1. Required field must exist (but may be null)
        if required and field not in data:
            errors.append(f"{field}: required but missing")
            continue

        # If field is present but null → acceptable
        value = data.get(field)
        if value is None:
            continue

        # 2. Type validation (only when value is not null)
        if expected_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"{field}: expected number")
        elif expected_type == "string" and not isinstance(value, str):
            errors.append(f"{field}: expected string")
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(f"{field}: expected boolean")
        elif expected_type == "date":
            # Accept ISO date strings only
            if not isinstance(value, str):
                errors.append(f"{field}: expected ISO date string")
        # Add enum validation
        enum_values = attr.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"{field}: must be one of {enum_values}")

    if errors:
        raise ValidationError(errors)
    

def fallback_llm_answer(message: str, model_json: dict) -> str:
    """
    A safe, domain-scoped fallback answerer.
    """

    # Normalize entities (list → dict)
    raw_entities = model_json.get("entities", {})
    if isinstance(raw_entities, list):
        entities = {e.get("id"): e for e in raw_entities}
    else:
        entities = raw_entities

    entity_names = ", ".join(entities.keys())

    prompt = f"""
You are a helpful assistant for a workflow automation platform.

You can answer general questions, but stay within the domain of:
- workflow automation
- the tenant's model
- the entities: {entity_names}

User message: "{message}"

Give a helpful, concise answer.
"""   
    return call_llm_and_parse_json(prompt)

