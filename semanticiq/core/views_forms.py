# semanticiq/core/views_forms.py
import json
from typing import Any, Dict, List

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from .models import Tenant, TenantModel
from .services.execution_agent import execute_intent
from .services.workflow_engine import EngineActor
from .models import Actor as ActorModel


# -------------------------------
# Normalization helpers
# -------------------------------

def _normalize_model(model_json: Any) -> Dict[str, Any]:
    """
    Accept dict | list | str -> return a dict (prefers an item with 'entities').
    Robust to how the model is stored in your registry (dict, list wrapper, or JSON text).
    """
    if isinstance(model_json, str):
        try:
            model_json = json.loads(model_json)
        except Exception:
            return {}
    if isinstance(model_json, list):
        # Prefer a dict that has 'entities'
        for item in model_json:
            if isinstance(item, dict) and "entities" in item:
                return item
        # Fallback: first dict
        for item in model_json:
            if isinstance(item, dict):
                return item
        return {}
    return model_json if isinstance(model_json, dict) else {}


def _entities_map(model_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Return name->spec regardless of 'entities' being a dict or a list.

    YOUR MODEL uses a LIST like:
      "entities": [
        {"id": "PurchaseOrder", "label": "...", "workflow": {...}, "attributes": [ ... ]},
        {"id": "Vendor", ...},
        ...
      ]
    We convert each item into a spec dict keyed by its id/name.
    """
    ents = model_doc.get("entities") or {}
    if isinstance(ents, dict):
        # Support alternative shapes: {"PurchaseOrder": {...}}
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in ents.items()}

    if isinstance(ents, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in ents:
            if not isinstance(item, dict):
                continue
            name = item.get("id") or item.get("name")
            if not name:
                continue
            # Treat "spec" as the item without 'id'/'name'
            spec = {k: v for k, v in item.items() if k not in ("id", "name")}
            out[str(name)] = spec
        return out

    return {}


def _attributes_map(spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Coerce attributes to a dict shape usable by the UI:
      - If dict -> as-is
      - If list of {id/type/...} or {name/type/...} -> {id_or_name: meta}
    YOUR MODEL uses a LIST of dicts with 'id'.
    """
    cand = spec.get("attributes")
    if isinstance(cand, dict):
        return cand
    if isinstance(cand, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in cand:
            if not isinstance(item, dict):
                continue
            nm = item.get("id") or item.get("name")
            if nm:
                out[str(nm)] = item
        return out

    # Fallbacks for alternative keys some models use
    for alt in ("properties", "props", "fields"):
        cand = spec.get(alt)
        if isinstance(cand, dict):
            return cand
        if isinstance(cand, list):
            out: Dict[str, Dict[str, Any]] = {}
            for item in cand:
                if isinstance(item, dict):
                    nm = item.get("id") or item.get("name")
                    if nm:
                        out[str(nm)] = item
            if out:
                return out

    # Nested JSON Schema fallback: spec.schema.properties
    schema = spec.get("schema")
    if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
        props = schema["properties"]
        required = set(schema.get("required", []) or [])
        out = {}
        for name, meta in props.items():
            m = meta if isinstance(meta, dict) else {}
            out[name] = {
                "type": (m.get("type") or "string"),
                "enum": m.get("enum") or [],
                "required": name in required,
                "label": m.get("title") or name,
            }
        return out

    return {}

# Helper to get or create Actor record
def get_or_create_actor(actor_id, actor_roles):
    actor, created = ActorModel.objects.get_or_create(
        identifier=actor_id,
        defaults={
            "actor_type": ActorModel.ActorType.USER,   # or infer from context
            "display_name": actor_id,
            "roles": actor_roles,
        }
    )

    # Optional: update roles if they changed
    if not created and actor.roles != actor_roles:
        actor.roles = actor_roles
        actor.save(update_fields=["roles"])

    return actor

def get_actor_for_user(user):
    try:
        return ActorModel.objects.get(user=user)
    except ActorModel.DoesNotExist:
        return None

# -------------------------------
# Views
# -------------------------------

def form_schema(request):
    """
    GET /runtime/form-schema?tenant_id=&model_id=&version=&entity=
    Returns a schema for form generation from ontology-light attributes.
    Response: {"entity": <name>, "fields": [ {name,type,required,options,label,default?,derived?}, ... ]}
    """
    tenant_id = request.GET.get("tenant_id")
    model_id = request.GET.get("model_id")
    version = request.GET.get("version", "1.0.0")
    entity = request.GET.get("entity")

    if not (tenant_id and model_id and entity):
        return HttpResponseBadRequest("tenant_id, model_id, entity required")
    
    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

    ontology = get_object_or_404(
        TenantModel,
        tenant=tenant,
        model_id=model_id,
        version=version,
        status="published",
    )

    model_doc = _normalize_model(ontology.json_data)
    ent_map = _entities_map(model_doc)

    # Exact match, then case-insensitive fallback
    spec = ent_map.get(entity)
    if not spec:
        lower_map = {k.lower(): k for k in ent_map.keys()}
        canon = lower_map.get(entity.lower()) if entity else None
        if canon:
            spec = ent_map.get(canon)

    if not spec:
        return HttpResponseBadRequest(f"No entity '{entity}' in model")

    attrs = _attributes_map(spec)
    if not attrs:
        return HttpResponseBadRequest(f"Entity '{entity}' has no attributes in the model")

    # Build fields for the UI
    fields: List[Dict[str, Any]] = []
    for name, meta in attrs.items():
        meta = meta if isinstance(meta, dict) else {}
        raw_t = meta.get("type") or "string"
        t = raw_t.lower() if isinstance(raw_t, str) else "string"
        required = bool(meta.get("required"))
        options = meta.get("enum") or meta.get("options") or []
        if not isinstance(options, list):
            options = []
        derived = bool(meta.get("derived"))  # your PO model includes `derived: true` for requiresDirectorApproval

        fields.append({
            "name": name,
            "type": t if t in ["string", "number", "integer", "boolean"] else "string",
            "required": required,
            "options": options,
            "label": meta.get("label", name),
            "default": meta.get("default", None),
            "derived": derived,
        })
    
    workflow = spec.get("workflow", {})
    states = [s.get("id") for s in workflow.get("states", [])]
    transitions = workflow.get("transitions", [])  

    if not fields:
        return HttpResponseBadRequest(f"No form fields could be derived for '{entity}'")

    return JsonResponse({"entity": entity, "fields": fields, "workflow": {"states": states,  "transitions": transitions,}})


@csrf_exempt
def form_submit(request):
    """
    POST /runtime/form-submit
    Body: { tenant_id, model_id, version?, entity, data, actor_id?, actor_roles? }
    Starts a workflow instance via Create<Entity>.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    tenant_id = payload.get("tenant_id")
    model_id = payload.get("model_id")
    version = payload.get("version", "1.0.0")
    entity = payload.get("entity")
    data = payload.get("data") or {}
    #actor_id = payload.get("actor_id", "anonymous")
    #actor_roles = payload.get("actor_roles", ["Requester"])  # default role for forms
    
    #actor_model = get_or_create_actor(actor_id, actor_roles)
    ##engine_actor = EngineActor.from_model(actor_model)

    actor_model = get_actor_for_user(request.user)
    engine_actor = EngineActor.from_model(actor_model)
    

    if not (tenant_id and model_id and entity):
        return HttpResponseBadRequest("tenant_id, model_id, entity required")
    
    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

    # Load and normalize model so executor/engine have the same view of the world
    ontology = get_object_or_404(
        TenantModel,
        tenant=tenant,
        model_id=model_id,
        version=version,
        status="published",
    )
    model_doc = _normalize_model(ontology.json_data)  
    

    # Build intent and pass model through via a non-conflicting key
    intent = {
        "intent": f"Create{entity}",
        "entity": entity,
        "event": payload.get("event"),
        "data": data,    
        "__model_json": model_doc,  # allows execute_intent to use the same model without changing its signature
    }

    result = execute_intent(
        tenant_id,
        model_id,
        version,
        intent,
        engine_actor,
        actor_model,
    )

    return JsonResponse(result)


