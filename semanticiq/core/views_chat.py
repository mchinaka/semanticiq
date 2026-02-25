# semanticiq/core/views_chat.py
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import TenantModel, Tenant
from .services.interpreter_agent import ValidationError, interpret, validate_entity_payload
from .services.execution_agent import execute_intent
from .models import Actor as ActorModel
from .services.workflow_engine import EngineActor
from .services.conversation_manager import ConversationManager, ConversationState
from .services.interpreter_agent import interpret, fallback_llm_answer
from .services.knowledge  import answer_knowledge_question


SESSION_STATE = {}

def get_actor_for_user(user):
    try:
        return ActorModel.objects.get(user=user)
    except ActorModel.DoesNotExist:
        return None

@csrf_exempt
def chat_endpoint(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        # -------------------------
        # Parse JSON
        # -------------------------
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")

        tenant_id = payload.get("tenant_id")
        model_id = payload.get("model_id")
        version = payload.get("version", "1.0.0")
        message = payload.get("message")
        print(">>> CHAT ENDPOINT CALLED:", message)
        actor_id = payload.get("actor_id")

        if not (tenant_id and model_id and message):
            return HttpResponseBadRequest("tenant_id, model_id, message required")

        # -------------------------
        # Load tenant + model
        # -------------------------
        tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
        if not tenant:
            return HttpResponseBadRequest("Tenant not found")

        try:
            ontology = TenantModel.objects.get(
                tenant=tenant,
                model_id=model_id,
                version=version,
                status="published"
            )
        except TenantModel.DoesNotExist:
            return HttpResponseBadRequest("Model not found/published")

        model_json = ontology.json_data

        # -------------------------
        # Resolve actor
        # -------------------------
        actor_model = get_actor_for_user(request.user)
        if not actor_model:
            return HttpResponseBadRequest("Actor not found")

        engine_actor = EngineActor.from_model(actor_model)

        # -------------------------
        # Load or create conversation state
        # -------------------------
        state = SESSION_STATE.get(actor_id)
        if state is None:
            state = ConversationState()
            SESSION_STATE[actor_id] = state

        conv_manager = ConversationManager(model_json)

        # =====================================================
        # A) If conversation is ONGOING → DO NOT interpret
        # =====================================================
        if not state.done:
            updated_state, reply = conv_manager.start_or_continue(state, message)
            SESSION_STATE[actor_id] = updated_state

            # Still collecting fields → return conversational reply
            if not updated_state.done:
                return JsonResponse({
                    "reply": reply,
                    "state": {
                        "entity": updated_state.entity,
                        "intent": updated_state.intent,
                        "data": updated_state.data,
                        "missing_fields": updated_state.missing_fields,
                        "awaiting_field": updated_state.awaiting_field,
                        "done": updated_state.done,
                    }
                })

            # Conversation finished → execute workflow
            final_intent = {
                "entity": updated_state.entity,
                "intent": updated_state.intent,
                "data": updated_state.data
            }

            try:
                validate_entity_payload(
                    model_json,
                    final_intent.get("entity"),
                    final_intent.get("data") or {}
                )
            except ValidationError as ve:
                return JsonResponse({"error": "Validation failed", "details": ve.errors}, status=400)

            result = execute_intent(
                tenant_id,
                model_id,
                version,
                final_intent,
                engine_actor,
                actor_model
            )

            SESSION_STATE[actor_id] = ConversationState()

            return JsonResponse({
                "reply": reply,
                "intent": final_intent,
                "result": result
            })

        # =====================================================
        # B) Conversation is NOT ongoing → NOW run interpreter
        # =====================================================
        print(">>> STATE BEFORE INTERPRET:", state.__dict__)
        intent = interpret(model_json, message)
        print("INTERPRET RESULT:", intent)
        intent_type = intent.get("intent_type")       

        # -------------------------
        # Knowledge intent
        # -------------------------
        if intent_type == "knowledge":
            answer = answer_knowledge_question(model_json, message, intent)
            return JsonResponse({"reply": answer})

        # -------------------------
        # Other intent → fallback assistant
        # -------------------------
        if intent_type == "other":
            answer = fallback_llm_answer(message, model_json)
            return JsonResponse({"reply": answer})

        # =====================================================
        # C) Action intent → start new workflow conversation
        # =====================================================
        state.entity = intent.get("entity")
        state.intent = intent.get("intent")
        state.data = intent.get("data") or {}
        state.awaiting_field = None
        state.missing_fields = []

        state.done = False


        updated_state, reply = conv_manager.start_or_continue(state, message)

        SESSION_STATE[actor_id] = updated_state

        if not updated_state.done:
            return JsonResponse({
                "reply": reply,
                "state": {
                    "entity": updated_state.entity,
                    "intent": updated_state.intent,
                    "data": updated_state.data,
                    "missing_fields": updated_state.missing_fields,
                    "awaiting_field": updated_state.awaiting_field,
                    "done": updated_state.done,
                }
            })

        # =====================================================
        # D) Action complete → execute workflow
        # =====================================================
        final_intent = {
            "entity": updated_state.entity,
            "intent": updated_state.intent,
            "data": updated_state.data
        }

        try:
            validate_entity_payload(
                model_json,
                final_intent.get("entity"),
                final_intent.get("data") or {}
            )
        except ValidationError as ve:
            return JsonResponse({"error": "Validation failed", "details": ve.errors}, status=400)

        result = execute_intent(
            tenant_id,
            model_id,
            version,
            final_intent,
            engine_actor,
            actor_model
        )

        SESSION_STATE[actor_id] = ConversationState()

        return JsonResponse({
            "reply": reply,
            "intent": final_intent,
            "result": result
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponseBadRequest("Internal error")