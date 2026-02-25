# semanticiq/core/views_registry.py
import json
import os
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, Http404
from django.conf import settings
from .models import TenantModel, TenantUser, Tenant
from .services.validator import validate_model
from .services.model_projection import project_model_to_entities
from .services.prompt_builder import build_model_from_prompt


# ---------- Helpers ----------

def _json_body(request, default="{}"):
    try:
        raw = request.body.decode("utf-8") if request.body else default
        return json.loads(raw)
    except Exception:
        return None

def _json_pointer_unescape(seg: str) -> str:
    # RFC 6901: "~1" -> "/", "~0" -> "~"
    return seg.replace("~1", "/").replace("~0", "~")

def _get_registry(tenant_id: str, model_id: str, status: str = None, version: str = None):
    qs = TenantModel.objects.filter(tenant_id=tenant_id, model_id=model_id)
    if status:
        qs = qs.filter(status=status)
    if version:
        qs = qs.filter(version=version)
    return qs

def _resource_template_path(name: str) -> Path:
    resources_dir = getattr(settings, "RESOURCES_DIR", None)
    if not resources_dir:
        return None

    base = Path(resources_dir) / "templates"

    if not name:
        return base  # return directory

    return base / f"{name}.json"

def _resolve_template_path(template_id: str):
    """
    Match template files by exact stem (everything before the final extension).
    Example:
      finance.template.json → stem = finance.template
      finance.json          → stem = finance
    """
    base_dir = _resource_template_path("")  # directory only
    if not base_dir or not base_dir.exists():
        return None

    for file in base_dir.iterdir():
        if file.stem == template_id:   # <-- EXACT MATCH
            return file

    return None

# ---------- Tenant users listing ----------

def tenant_users(request):
    tenant_id = request.GET.get("tenant_id")
    if not tenant_id:
        return JsonResponse({"error": "tenant_id is required"}, status=400)

    try:
        tenant = Tenant.objects.get(tenant_id=tenant_id)
    except Tenant.DoesNotExist:
        return JsonResponse({"error": "Tenant not found"}, status=404)

    # Fetch users belonging to this tenant
    memberships = TenantUser.objects.filter(tenant=tenant).select_related("user")  

    users = []
    for m in memberships:
        u = m.user
        users.append({
            "user_id": u.id,
            "username": u.username,
            "full_name": f"{u.first_name} {u.last_name}".strip(),
            "email": u.email,
        })

    return JsonResponse(users, safe=False)

# ---------- Template listing ----------

@require_http_methods(["GET"])
def list_templates(request):
    """
    Dynamically scans the resources/templates directory and returns
    all template filenames (without extensions).
    """
    # Path to your template directory
    template_dir = os.path.join(settings.BASE_DIR, "resources", "templates")

    if not os.path.isdir(template_dir):
        return JsonResponse({"templates": [], "error": "template directory not found"}, status=200)

    # Allowed template file extensions
    allowed_ext = {".json", ".yaml", ".yml", ".mvp"}

    templates = []
    for filename in os.listdir(template_dir):
        name, ext = os.path.splitext(filename)
        if ext.lower() in allowed_ext:
            templates.append(name)

    return JsonResponse({"templates": templates})

# ---------- Create draft ----------

@csrf_exempt
@require_http_methods(["POST"])
def create_model(request, tenantId):
    """
    Create a draft model.
    If no 'entities' provided, load the selected template (any extension).
    No fallback to procurement.
    """
    body = _json_body(request)
    if body is None:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    model_id = body.get("modelId") or "new-model"
    template_id = (body.get("templateId") or body.get("template"))  # NEW
    data = body.get("json") or body

    # If no entities provided, load the selected template
    if not isinstance(data, dict) or not data.get("entities"):

        if not template_id:
            return JsonResponse({
                "ok": False,
                "error": "No templateId provided and no entities supplied"
            }, status=400)

        # Dynamically resolve template file (any extension)
        tmpl_path = _resolve_template_path(template_id)
        if not tmpl_path:
            return JsonResponse({
                "ok": False,
                "error": f"Template '{template_id}' not found"
            }, status=400)

        with open(tmpl_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Normalize root
        data = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(data, dict):
            return JsonResponse({
                "ok": False,
                "error": "Template root must be an object or array containing an object"
            }, status=400)

    # Inject metadata
    data["tenant_id"] = tenantId
    data["model_id"] = model_id
    data.setdefault("version", "draft")

    tm = TenantModel.objects.create(
        tenant_id=tenantId,
        model_id=model_id,
        version=data.get("version", "draft"),
        status="draft",
        json_data=data,
    )

    return JsonResponse({
        "ok": True,
        "tenantId": tenantId,
        "modelId": tm.model_id,
        "version": tm.version,
        "status": tm.status
    }, status=201)

# ---------- Create model from prompt (AI-assisted) ----------
@csrf_exempt
@require_http_methods(["POST"])
def create_model_from_prompt(request, tenantId):
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    model_id = body.get("modelId")
    prompt = body.get("prompt")
    template_id = body.get("templateId")

    if not model_id or not prompt:
        return JsonResponse({"ok": False, "error": "modelId and prompt required"}, status=400)

    # Call service layer
    try:
        model_json = build_model_from_prompt(prompt, template_id)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    # Inject modelId BEFORE validation
    model_json["modelId"] = model_id

    # Validate
    ok, errors = validate_model(model_json)
    if not ok:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    # Save
    tm = TenantModel.objects.create(
        tenant_id=tenantId,
        model_id=model_id,
        version="draft",
        status="draft",
        json_data=model_json,
    )

    return JsonResponse({
        "ok": True,
        "tenantId": tenantId,
        "modelId": model_id,
        "version": "draft",
        "status": "draft",
    }, status=201)

# ---------- List models ----------
@require_http_methods(["GET"])
def list_models(request, tenantId):
    """
    Returns all models for a tenant, including draft and published versions.
    """
    models = (
        TenantModel.objects
        .filter(tenant_id=tenantId)
        .order_by("model_id", "-status", "-version")
    )

    payload = []
    for m in models:
        payload.append({
            "model_id": m.model_id,
            "status": m.status,
            "version": m.version,
        })

    return JsonResponse({"models": payload})

# ---------- Get model (draft by default, allow status/version via query) ----------

#@require_http_methods(["GET"])
#def get_model(request, tenantId, modelId):
    #status = request.GET.get("status") or "draft"  # default draft
    #version = request.GET.get("version")  # optional
    #qs = _get_registry(tenantId, modelId, status=status, version=version)
    #tm = get_object_or_404(qs)
    #return JsonResponse(tm.json_data)

@require_http_methods(["GET"])
def get_model(request, tenantId, modelId):
    status = request.GET.get("status")
    version = request.GET.get("version")

    # Clean empty query params
    if status == "":
        status = None
    if version == "":
        version = None

    # 1. If version explicitly requested → return that version
    if version:
        tm = get_object_or_404(
            TenantModel,
            tenant_id=tenantId,
            model_id=modelId,
            version=version
        )
        return JsonResponse(tm.json_data)

    # 2. If status explicitly requested → return that status
    if status:
        tm = get_object_or_404(
            TenantModel,
            tenant_id=tenantId,
            model_id=modelId,
            status=status
        )
        return JsonResponse(tm.json_data)

    # 3. Default: return draft if exists
    draft = TenantModel.objects.filter(
        tenant_id=tenantId,
        model_id=modelId,
        status="draft"
    ).first()
    if draft:
        return JsonResponse(draft.json_data)

    # 4. Fallback: return latest published
    published = TenantModel.objects.filter(
        tenant_id=tenantId,
        model_id=modelId,
        status="published"
    ).order_by("-version").first()

    if not published:
        raise Http404("Model not found")

    return JsonResponse(published.json_data)

# ---------- Update draft ----------

@csrf_exempt
@require_http_methods(["PUT"])
def update_model(request, tenantId, modelId):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    qs = _get_registry(tenantId, modelId, status="draft")
    tm = get_object_or_404(qs)

    # Optional: validate before saving
    ok, errors = validate_model(body)
    if not ok:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    # Save JSON
    tm.json_data = body
    tm.save()

    # NEW: regenerate EntityDefinition + EntityRelationship
    project_model_to_entities(tm)

    return JsonResponse({
        "ok": True,
        "tenantId": tenantId,
        "modelId": modelId,
        "version": tm.version,
        "status": tm.status,
        "model": tm.json_data
    })

# ---------- Validate draft ----------

@csrf_exempt
@require_http_methods(["POST"])
def validate_draft(request, tenantId, modelId):
    qs = _get_registry(tenantId, modelId, status="draft")
    tm = get_object_or_404(qs)
    ok, errors = validate_model(tm.json_data)
    return JsonResponse({"ok": ok, "errors": errors}, status=200 if ok else 400)

# ---------- JSON Patch (RFC 6902-ish) ----------

@csrf_exempt
@require_http_methods(["PATCH"])
def patch_model(request, tenantId, modelId):
    qs = _get_registry(tenantId, modelId, status="draft")
    tm = get_object_or_404(qs)
    ops = _json_body(request, default="[]")
    if ops is None or not isinstance(ops, list):
        return JsonResponse({"ok": False, "error": "Invalid JSON patch array"}, status=400)

    def _get(doc, seg):
        seg = _json_pointer_unescape(seg)
        if isinstance(doc, list):
            if seg == "-":
                return doc, "-"
            try:
                idx = int(seg)
            except ValueError:
                raise TypeError(f"List path expected integer index, got '{seg}'")
            if idx < 0 or idx > len(doc):
                # allow idx == len(doc) only for 'add' insert; actual op checks later
                pass
            return doc[idx] if idx < len(doc) else None, idx
        elif isinstance(doc, dict):
            return doc.get(seg), seg
        else:
            raise TypeError("Unexpected node type in document")

    def navigate_parent(root, parts):
        if not parts:
            return root, None
        cur = root
        for seg in parts[:-1]:
            node, key = _get(cur, seg)
            if node is None:
                # lazily create dict nodes
                seg_unesc = _json_pointer_unescape(seg)
                if isinstance(cur, dict):
                    cur[seg_unesc] = {}
                    node = cur[seg_unesc]
                else:
                    raise KeyError(f"Cannot auto-create path under non-dict for segment '{seg_unesc}'")
            cur = node
        last = parts[-1]
        return cur, last

    def apply_op(doc, op):
        if "op" not in op or "path" not in op:
            raise ValueError("Patch operation missing 'op' or 'path'")
        path = op["path"]
        parts = [p for p in path.strip("/").split("/") if p != ""]
        parent, last = navigate_parent(doc, parts)

        if op["op"] == "add":
            value = op.get("value")
            if isinstance(parent, list):
                if last == "-":
                    parent.append(value)
                else:
                    idx = int(last)
                    if idx < 0 or idx > len(parent):
                        raise IndexError(f"Add index {idx} out of range")
                    parent.insert(idx, value)
            elif isinstance(parent, dict):
                parent[_json_pointer_unescape(last)] = value
            else:
                raise TypeError("Add parent must be list or dict")

        elif op["op"] == "replace":
            value = op.get("value")
            if isinstance(parent, list):
                idx = int(last)
                if idx < 0 or idx >= len(parent):
                    raise IndexError(f"Replace index {idx} out of range")
                parent[idx] = value
            elif isinstance(parent, dict):
                parent[_json_pointer_unescape(last)] = value
            else:
                raise TypeError("Replace parent must be list or dict")

        elif op["op"] == "remove":
            if isinstance(parent, list):
                if last in ("-", None):
                    raise ValueError("Cannot remove '-' or root")
                idx = int(last)
                if idx < 0 or idx >= len(parent):
                    raise IndexError(f"Remove index {idx} out of range")
                parent.pop(idx)
            elif isinstance(parent, dict):
                parent.pop(_json_pointer_unescape(last), None)
            else:
                raise TypeError("Remove parent must be list or dict")

        else:
            raise ValueError(f"Unsupported op: {op['op']}")

    try:
        doc = tm.json_data
        for op in ops:
            apply_op(doc, op)

        # Optional: validate after patch
        ok, errors = validate_model(doc)
        if not ok:
            return JsonResponse({"ok": False, "errors": errors}, status=400)

        tm.json_data = doc
        tm.save()
        project_model_to_entities(tm)
        return JsonResponse({"ok": True, "tenantId": tenantId, "modelId": modelId, "version": tm.version, "status": tm.status, "model": tm.json_data})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

# ---------- Publish (simple) ----------

@csrf_exempt
@require_http_methods(["POST"])
def publish_model(request, tenantId, modelId):

    draft = get_object_or_404(
        TenantModel.objects.filter(tenant_id=tenantId, model_id=modelId, status="draft")
    )

    # Find latest published version
    latest = (
        TenantModel.objects
        .filter(tenant_id=tenantId, model_id=modelId, status="published")
        .order_by("-created_at")
        .first()
    )

    def bump(version):
        major, minor, patch = map(int, version.split("."))
        return f"{major}.{minor}.{patch + 1}"

    new_version = bump(latest.version) if latest else "1.0.0"

    published = TenantModel.objects.create(
        tenant_id=draft.tenant_id,
        model_id=draft.model_id,
        version=new_version,
        status="published",
        json_data=draft.json_data,
    )

    return JsonResponse({
        "ok": True,
        "tenantId": tenantId,
        "modelId": modelId,
        "version": published.version,
        "status": published.status
    })

# ---------- List prompt templates ----------
@require_http_methods(["GET"])
def list_prompt_templates(request):
    """
    Returns a list of available LLM prompt templates.
    """
    templates = [
        {
            "id": "process_model",
            "name": "Process Model",
            "description": "For describing multi-step business processes with entities, states, and transitions."
        },
        {
            "id": "approval_workflow",
            "name": "Approval Workflow",
            "description": "For describing approval chains, roles, and decision logic."
        },
        {
            "id": "master_data",
            "name": "Master Data Entity",
            "description": "For describing core business objects with attributes and relationships."
        },
        {
            "id": "integration_flow",
            "name": "Integration / Data Flow",
            "description": "For describing data ingestion, mapping, and transformation flows."
        }
    ]
    return JsonResponse({"templates": templates})