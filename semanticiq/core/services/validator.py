# semanticiq/core/services/validator.py
import json
from typing import Dict, List, Any, Tuple
from jsonschema import validate as jsonschema_validate, ValidationError
from django.conf import settings

ALLOWED_REL_TYPES = {"references", "aggregates", "dependsOn", "parentOf", "childOf"}
ALLOWED_CARDINALITY = {"one-to-one", "one-to-many", "many-to-one", "many-to-many"}

class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Validation failed")
        self.errors = errors

def _collect_entities(model: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e["id"]: e for e in model.get("entities", []) if isinstance(e, dict) and "id" in e}

def _attr_ids(entity: Dict[str, Any]) -> set:
    return {a["id"] for a in entity.get("attributes", []) if isinstance(a, dict) and "id" in a}

def _vars_in_expr(expr: Any) -> List[str]:
    """Recursively collect all 'var' references from JSONLogic-like expressions."""
    found = []
    if isinstance(expr, dict):
        for k, v in expr.items():
            if k == "var":
                if isinstance(v, str):
                    found.append(v)
                elif isinstance(v, dict) and "var" in v:
                    found.append(v["var"])
            else:
                found.extend(_vars_in_expr(v))
    elif isinstance(expr, list):
        for item in expr:
            found.extend(_vars_in_expr(item))
    return found

def _check_relationships(model: Dict[str, Any]) -> List[str]:
    errors = []
    entities = _collect_entities(model)
    for e in entities.values():
        rels = e.get("relationships", []) or []
        for r in rels:
            rid = r.get("id", "<no-id>")
            typ = r.get("type")
            to  = r.get("to")
            if typ not in ALLOWED_REL_TYPES:
                errors.append(f'Relationship "{rid}" has invalid type "{typ}".')
            if not to or to not in entities:
                errors.append(f'Relationship "{rid}" targets missing entity "{to}".')
            card = r.get("cardinality")
            if card and card not in ALLOWED_CARDINALITY:
                errors.append(f'Relationship "{rid}" has invalid cardinality "{card}".')
            km = r.get("keyMapping", {}) or {}
            from_attr = km.get("fromAttr")
            to_attr   = km.get("toAttr")
            if from_attr and from_attr not in _attr_ids(e):
                errors.append(f'Relationship "{rid}" keyMapping.fromAttr "{from_attr}" not found on entity "{e.get("id")}".')
            if to_attr and to and to_attr not in _attr_ids(entities[to]):
                errors.append(f'Relationship "{rid}" keyMapping.toAttr "{to_attr}" not found on entity "{to}".')
    return errors

def _check_workflow_and_rules(model: Dict[str, Any]) -> List[str]:
    """
    Rules: ensure referenced vars are plausible (attribute names or dotted cross-refs).
    Workflow guards: **RELAXED** — allow payload-only vars (e.g., 'approvalRole').
    """
    errors = []
    entities = _collect_entities(model)
    for e in entities.values():
        attrs = _attr_ids(e)
        # Rules checks (keep strict-ish)
        for r in e.get("rules", []) or []:
            rid = r.get("id", "<no-id>")
            expr = r.get("expr")
            for var_name in _vars_in_expr(expr):
                # allow dotted Supplier.riskRating style; only check first segment
                base = var_name.split(".")[0]
                # relax cross-entity list as needed
                allowed_bases = attrs | {"Supplier", "Vendor", "Approval", "User", "Department"}
                if base not in allowed_bases:
                    errors.append(f'Rule "{rid}" on "{e.get("id")}" references unknown var "{var_name}".')
        # Workflow guards — relaxed: don't error if var not in attrs (payload-driven is valid)
        wf = e.get("workflow", {}) or {}
        for t in wf.get("transitions", []) or []:
            expr = (t.get("guard") or {}).get("expr")
            # intentionally **no error** for unknown vars in guards
            # (operators may pass payload fields like 'approvalRole')
            _ = expr
    return errors

def validate_model(model: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    # 1) JSON Schema validation
    try:
        schema_path = settings.RESOURCES_DIR / "ontology-lite.schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        jsonschema_validate(instance=model, schema=schema)
    except FileNotFoundError:
        errors.append("Schema file not found at resources/ontology-lite.schema.json.")
    except ValidationError as e:
        errors.append(f"Schema validation error: {e.message}")

    # 2) Referential checks (relationships, rules; guards relaxed)
    errors.extend(_check_relationships(model))
    errors.extend(_check_workflow_and_rules(model))

    return (len(errors) == 0, errors)
