# extractors.py
from typing import Callable, Dict, Any, Optional
import re
from datetime import datetime

Extractor = Callable[[str], Optional[Any]]

TYPE_EXTRACTORS: Dict[str, Extractor] = {}

TAG_EXTRACTORS: Dict[str, Extractor] = {}


def register_type_extractor(type_name: str):
    def decorator(fn: Extractor):
        TYPE_EXTRACTORS[type_name] = fn
        return fn
    return decorator


def register_tag_extractor(tag_name: str):
    def decorator(fn: Extractor):
        TAG_EXTRACTORS[tag_name] = fn
        return fn
    return decorator


@register_type_extractor("number")
def extract_number(text: str) -> Optional[float]:
    m = re.search(r"[-+]?\d[\d,]*(\.\d+)?", text)
    if not m:
        return None
    value = m.group(0).replace(",", "")
    try:
        return float(value)
    except ValueError:
        return None


@register_type_extractor("currency")
def extract_currency_amount(text: str) -> Optional[float]:
    m = re.search(r"[€$£]\s*([\d,]+(\.\d+)?)", text)
    if not m:
        return None
    value = m.group(1).replace(",", "")
    try:
        return float(value)
    except ValueError:
        return None


@register_type_extractor("date")
def extract_date(text: str) -> Optional[str]:
    # naive example; you can improve this
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if not m:
        return None
    return m.group(1)


@register_type_extractor("boolean")
def extract_boolean(text: str) -> Optional[bool]:
    lowered = text.lower()
    if "yes" in lowered or "true" in lowered:
        return True
    if "no" in lowered or "false" in lowered:
        return False
    return None


@register_type_extractor("string")
def extract_free_text(text: str) -> Optional[str]:
    # IMPORTANT: default to None to avoid garbage
    return None


# --- Tag-based extractors ---

@register_tag_extractor("identifier")
def extract_identifier(text: str) -> Optional[str]:
    # Example: pick first uppercase-ish token
    m = re.search(r"\b[A-Z][A-Z0-9\-]{2,}\b", text)
    return m.group(0) if m else None


@register_tag_extractor("currency")
def extract_currency_code(text: str) -> Optional[str]:
    m = re.search(r"\b(EUR|USD|GBP)\b", text, re.I)
    return m.group(1).upper() if m else None


def get_type_extractor(type_name: str) -> Optional[Extractor]:
    return TYPE_EXTRACTORS.get(type_name)


def get_tag_extractor(tag_name: str) -> Optional[Extractor]:
    return TAG_EXTRACTORS.get(tag_name)


def extract_entity_from_text(model_json: dict, text: str) -> str | None:
    raw_entities = model_json.get("entities", {})
    if isinstance(raw_entities, list):
        entities = {e.get("id"): e for e in raw_entities}
    else:
        entities = raw_entities

    t = text.lower()

    for ename in entities.keys():
        if not ename:
            continue

        # direct match
        if ename.lower() in t:
            return ename

        # spaced version: PurchaseOrder → "purchase order"
        spaced = re.sub(r"([A-Z])", r" \1", ename).strip().lower()
        if spaced in t:
            return ename

    return None