import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import Tenant, TenantModel, WorkflowInstance, TransitionLog
from .models import Actor as ActorModel
from .services.workflow_engine import EngineActor, WorkflowEngine, get_actor_for_user #execute_transition
from .services.execution_agent import execute_transition
from typing import Any, Dict, List
from django.shortcuts import render, redirect
from .models import TenantUser
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404

from .roles import (
    TENANT_ROLE_ADMIN,
    TENANT_ROLE_DEVELOPER,
    TENANT_ROLE_RUNTIME,
)

# Helper to get Actor record for a Django user
def get_actor_for_user(user):
    try:
        return ActorModel.objects.get(user=user)
    except ActorModel.DoesNotExist:
        return None

@require_http_methods(["GET"])
def runtime_page(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("login")

    # Fetch all tenant memberships for this user
    memberships = (
        TenantUser.objects
        .filter(user=user)
        .select_related("tenant")
    )

    if not memberships.exists():
        return render(request, "core/no_access.html")

    # Determine selected tenant
    if memberships.count() == 1:
        # Auto-select the only tenant
        tuser = memberships.first()
        tenant = tuser.tenant
        available_tenants = [tenant]

        # Store in session for consistency
        request.session["tenant_id"] = tenant.tenant_id

    else:
        # User has multiple tenants
        available_tenants = [m.tenant for m in memberships]

        # Allow switching via ?tenant_id=... or session
        selected_id = request.GET.get("tenant_id") or request.session.get("tenant_id")

        # Pick tenant: selected → session → fallback to first
        tenant = next(
            (t for t in available_tenants if str(t.tenant_id) == str(selected_id)),
            available_tenants[0]
        )

        # Update session with the selected tenant
        request.session["tenant_id"] = tenant.tenant_id

        # Get the TenantUser record for this tenant
        tuser = memberships.filter(tenant=tenant).first()

    # Extract roles
    roles = set(tuser.roles.values_list("role", flat=True))

    # ---------------------------------------------------------
    # ACTOR LOGIC (unchanged)
    # ---------------------------------------------------------
    actor = get_actor_for_user(user)

    # ---------------------------------------------------------

    # Fetch published models for this tenant
    models = list(
        TenantModel.objects
        .filter(tenant=tenant, status="published")
        .order_by("-updated_at")
        .values("model_id", "version", "status")
    )

    # Fallback to drafts if no published models
    if not models:
        models = list(
            TenantModel.objects
            .filter(tenant=tenant, status="draft")
            .order_by("-updated_at")
            .values("model_id", "version", "status")
        )

    return render(request, "core/runtime.html", {
        # Tenant context
        "tenant": tenant,
        "tenant_id": tenant.tenant_id,
        "tenant_name": tenant.name,
        "available_tenants": available_tenants,

        # Roles
        "roles": roles,
        "is_admin": TENANT_ROLE_ADMIN in roles,
        "is_developer": TENANT_ROLE_DEVELOPER in roles,
        "is_runtime": TENANT_ROLE_RUNTIME in roles,

        # Actor
        "actor_id": actor.identifier,
        "actor_roles": actor.roles,

        # Models
        "models": models,
    })

def _active_model(tenant_id):
    tm = TenantModel.objects.filter(tenant_id=tenant_id, status='published').order_by('-updated_at').first()
    return tm.json_data if tm else None

@csrf_exempt
@require_http_methods(["POST"]) 
def start_workflow(request, tenantId, name):
    payload = json.loads(request.body.decode('utf-8') or '{}')
    model = _active_model(tenantId)
    if not model:
        return JsonResponse({"ok": False, "error": "No active model"}, status=400)
    engine = WorkflowEngine(model)
    inst = engine.start(name, payload)
    wi = WorkflowInstance.objects.create(
        tenant_id=tenantId,
        workflow_name=name,
        instance_id=inst['instanceId'],
        state=inst['state'],
        payload=inst['payload']
    )
    return JsonResponse({"ok": True, "instanceId": wi.instance_id, "state": wi.state})

@csrf_exempt
@require_http_methods(["POST"]) 
def signal_workflow(request, tenantId, name, instanceId):
    wi = get_object_or_404(WorkflowInstance, tenant_id=tenantId, workflow_name=name, instance_id=instanceId)
    payload_update = json.loads(request.body.decode('utf-8') or '{}')
    wi.payload.update(payload_update)
    model = _active_model(tenantId)
    engine = WorkflowEngine(model)
    nxt = engine.next(name, wi.state, wi.payload)
    wi.state = nxt['state']
    wi.save()
    return JsonResponse({"ok": True, "state": wi.state, "actions": nxt.get('actions', [])})

@require_http_methods(["GET"]) 
def get_state(request, tenantId, name, instanceId):
    wi = get_object_or_404(WorkflowInstance, tenant_id=tenantId, workflow_name=name, instance_id=instanceId)
    return JsonResponse({"state": wi.state, "payload": wi.payload})


def _normalize_model(model_json: Any) -> Dict[str, Any]:
    """Accept dict | list | str -> dict. Prefer item with 'entities'."""
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
    return model_json if isinstance(model_json, dict) else {}

def _entities_map(model_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return name->spec regardless of entities being dict or list."""
    ents = model_doc.get("entities") or {}
    if isinstance(ents, dict):
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in ents.items()}
    if isinstance(ents, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in ents:
            if not isinstance(item, dict):
                continue
            name = item.get("id") or item.get("name")
            if not name:
                continue
            spec = item.get("spec")
            if not isinstance(spec, dict):
                spec = {k: v for k, v in item.items() if k not in ("id", "name")}
            out[str(name)] = spec if isinstance(spec, dict) else {}
        return out
    return {}

def list_entities(request):
    """
    GET /runtime/entities?tenant_id=&model_id=&version=
    Returns: { "entities": ["PurchaseOrder", ...] }
    """
    tenant_id = request.GET.get("tenant_id")
    model_id  = request.GET.get("model_id")
    version   = request.GET.get("version", "1.0.0")

    if not (tenant_id and model_id):
        return HttpResponseBadRequest("tenant_id, model_id required")
    
    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

    tm = get_object_or_404(
        TenantModel,
        tenant=tenant, model_id=model_id,
        version=version, status="published"
    )
    model_doc = _normalize_model(tm.json_data)
    ent_map = _entities_map(model_doc)
    names = sorted(ent_map.keys())

    if not names:
        # Give a clear signal to UI that there are no entities
        return HttpResponseBadRequest("Model has no entities")

    return JsonResponse({"entities": names})

def list_workflows(request):
    actor_model = get_actor_for_user(request.user)
    engine_actor = EngineActor.from_model(actor_model)

    actor_id = actor_model.identifier
    print("Workflows for:", actor_id)

    workflows = WorkflowInstance.objects.filter(
        created_by=actor_id
    ).order_by("-updated_at").values(
        "instance_id",
        "entity",
        "state",
        "created_at",
        "updated_at",
        "payload"
    )

    return JsonResponse(list(workflows), safe=False)
    
def pending_approvals(request):
    actor_model = get_actor_for_user(request.user)
    engine_actor = EngineActor.from_model(actor_model)

    # Use the logged-in actor's identifier
    actor_id = actor_model.identifier
    print("Pending approvals for:", actor_id)

    workflows = WorkflowInstance.objects.filter(
        state="Submitted",
        payload__approver=actor_id
    ).order_by("-updated_at").values(
        "instance_id",
        "entity",
        "state",
        "created_by",
        "created_at",
        "updated_at",
        "payload"
    )

    return JsonResponse(list(workflows), safe=False)

@require_GET
def get_workflow(request, workflow_id):
    try:
        wf = WorkflowInstance.objects.get(instance_id=workflow_id)
    except WorkflowInstance.DoesNotExist:
        return JsonResponse({"error": "Workflow not found"}, status=404)

    response = {
        "instance_id": wf.instance_id,
        "entity": wf.entity,
        "state": wf.state,
        "created_at": wf.created_at,
        "updated_at": wf.updated_at,
        "payload": wf.payload,
        "history": wf.history or []
    }

    return JsonResponse(response)

@csrf_exempt
def transition(request):
    """
    POST /runtime/transition
    Body: {
      tenant_id,
      model_id,
      version?,
      instance_id,
      event
    }
    Applies an event (approve/reject/etc.) to an existing workflow instance.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    tenant_id   = payload.get("tenant_id")
    model_id    = payload.get("model_id")
    version     = payload.get("version", "1.0.0")
    instance_id = payload.get("instance_id")
    event       = payload.get("event")

    if not (tenant_id and model_id and instance_id and event):
        return HttpResponseBadRequest("tenant_id, model_id, instance_id, event required")

    # Resolve actor from logged-in user
    actor_model = get_actor_for_user(request.user)
    if actor_model is None:
        return JsonResponse({"error": "No Actor record for this user"}, status=400)

    engine_actor = EngineActor.from_model(actor_model)

    # Load tenant + model
    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
    ontology = get_object_or_404(
        TenantModel,
        tenant=tenant,
        model_id=model_id,
        version=version,
        status="published",
    )

    print("TRANSITION DEBUG:",
      "event=", event,
      "instance_id=", instance_id,
      "actor_id=", actor_model.identifier,
      "actor_roles=", actor_model.roles)

    # Execute transition via engine helper
    try:
        result = execute_transition(
            tenant=tenant,
            ontology=ontology,
            instance_id=instance_id,
            event=event,
            actor=engine_actor,
            actor_model=actor_model,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(result)