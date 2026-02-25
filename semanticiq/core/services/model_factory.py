import json
from typing import Any, Dict, Optional
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from ..models import TenantModel
from .validator import validate_model
from .spreadsheet_parser import build_model_from_spreadsheet
from .datasource_connector import build_model_from_data_source


# Create model from spreadsheet upload
@csrf_exempt
@require_http_methods(["POST"])
def create_model_from_spreadsheet(request, tenantId):
    model_id = request.POST.get("modelId")
    file = request.FILES.get("file")

    if not model_id or not file:
        return JsonResponse({"ok": False, "error": "modelId and file required"}, status=400)

    try:
        model_json = build_model_from_spreadsheet(file)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    ok, errors = validate_model(model_json)
    if not ok:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    tm = TenantModel.objects.create(
        tenant_id=tenantId,
        model_id=model_id,
        version="draft",
        status="draft",
        json_data=model_json,
    )

    return JsonResponse({"ok": True, "tenantId": tenantId, "modelId": model_id}, status=201)

# Create model from data source (e.g., external API, database)
@csrf_exempt
@require_http_methods(["POST"])
def create_model_from_data(request, tenantId):
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    model_id = body.get("modelId")
    source_type = body.get("sourceType")

    if not model_id or not source_type:
        return JsonResponse({"ok": False, "error": "modelId and sourceType required"}, status=400)

    try:
        model_json = build_model_from_data_source(source_type, body)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    ok, errors = validate_model(model_json)
    if not ok:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    tm = TenantModel.objects.create(
        tenant_id=tenantId,
        model_id=model_id,
        version="draft",
        status="draft",
        json_data=model_json,
    )

    return JsonResponse({"ok": True, "tenantId": tenantId, "modelId": model_id}, status=201)