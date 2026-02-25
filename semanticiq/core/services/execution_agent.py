# semanticiq/core/services/execution_agent.py
import json
from typing import Dict, Any
from django.utils import timezone
from django.shortcuts import get_object_or_404
from ..models import EntityInstance, TenantModel, WorkflowInstance, TransitionLog, Tenant
from ..models import Actor as ActorModel
from .workflow_engine import WorkflowEngine, EngineActor, WorkflowError
import uuid

def _load_engine(ontology: TenantModel) -> WorkflowEngine:
    return WorkflowEngine(ontology.json_data)

def execute_intent(tenant_id: str, model_id: str, version: str, intent: Dict[str, Any], actor: EngineActor, actor_model: ActorModel) -> Dict[str, Any]:
    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
    ontology = get_object_or_404(TenantModel, tenant=tenant, model_id=model_id, version=version, status="published")
    engine = _load_engine(ontology)    

    entity = intent.get("entity")
    data = intent.get("data") or {}
    event = intent.get("event")   
    intent_name = intent.get("intent", "")  

    if intent_name.startswith("Create"):
        state = engine.initial_state(entity)

        entity_instance = EntityInstance.objects.create(
            tenant_model=ontology,
            entity_type=entity,
            data=data,
            state=state,
            actor=actor_model,
            created_by=actor_model.identifier,
            updated_by=actor_model.identifier,
            
        )
        
        instance = WorkflowInstance.objects.create(
            tenant_model=ontology,
            entity=entity,
            state=state,
            payload=data,
            actor=actor_model,
            roles=actor.roles,
            instance_id=str(uuid.uuid4()),
            model_version=version,
            created_by=actor_model.identifier,
            updated_by=actor_model.identifier,
        )
        

        if event and event != state:           
            try:
                result = engine.next(
                    entity_id = entity,
                    current_state = state,
                    payload=instance.payload,
                    event=event,   # <-- correct
                )                

                to_state = result.get("to_state") or result.get("state") or state
                from_state = state
                state = to_state

                instance.state = to_state
                instance.save(update_fields=["state"])
                instance.updated_by = actor_model.identifier
                instance.save(update_fields=["state", "updated_by"])


                entity_instance.state = to_state
                entity_instance.save(update_fields=["state"])
                entity_instance.updated_by = actor_model.identifier
                entity_instance.save(update_fields=["state", "updated_by"])

                TransitionLog.objects.create(
                    instance=instance,
                    from_state=from_state,
                    to_state=to_state,
                    event=event,
                    actor=actor_model,
                    actor_roles=actor.roles,
                    guard_passed=True,
                    reason="auto-transition on create",
                    payload={"data": data}
                )

            except WorkflowError as e:
                TransitionLog.objects.create(
                    instance=instance,
                    from_state=state,
                    to_state=state,
                    event=event,
                    actor=actor_model,
                    actor_roles=actor.roles,
                    guard_passed=False,
                    reason=str(e),
                    payload={"data": data}
                )

        return {
            "action": "started",
            "instance_id": instance.id,
            "entity_instance_id": entity_instance.id,
            "entity": entity,
            "state": state,
            "data": data
        }


def execute_transition(
    tenant: Tenant,
    ontology: TenantModel,
    instance_id: str,
    event: str,
    actor: EngineActor,
    actor_model: ActorModel
) -> Dict[str, Any]:

    # Load engine
    engine = _load_engine(ontology)
    engine.actor = actor_model

    # 1. Load workflow instance
    try:
        instance = WorkflowInstance.objects.get(
            tenant_model=ontology,
            instance_id=instance_id
        )
    except WorkflowInstance.DoesNotExist:
        raise Exception(f"Workflow instance {instance_id} not found")

    entity = instance.entity
    current_state = instance.state
    payload = instance.payload or {}

    # 2. Load entity instance 
    try:
        entity_instance = EntityInstance.objects.get(
            tenant_model=ontology,
            entity_type=entity,
            id=instance.entity_instance_id if hasattr(instance, "entity_instance_id") else None
        )
    except Exception:
        entity_instance = None   

    # 3. Apply transition using engine.next()
    try:
        result = engine.next(
            entity_id=entity,
            current_state=current_state,
            payload=payload,
            event=event
        )

        to_state = (
            result.get("to_state")
            or result.get("state")
            or current_state
        )

        from_state = current_state

        # 4. Update workflow instance
        instance.state = to_state
        instance.updated_by = actor_model.identifier
        instance.save(update_fields=["state", "updated_by"])

        # 5. Update entity instance (if exists)
        if entity_instance:
            entity_instance.state = to_state
            entity_instance.updated_by = actor_model.identifier
            entity_instance.save(update_fields=["state", "updated_by"])        

        # 6. Log transition
        TransitionLog.objects.create(
            instance=instance,
            from_state=from_state,
            to_state=to_state,
            event=event,
            actor=actor_model,
            actor_roles=actor.roles,
            guard_passed=True,
            reason="transition",
            payload={"data": payload}
        )     
        

    except WorkflowError as e:
        # Log failed transition
        TransitionLog.objects.create(
            instance=instance,
            from_state=current_state,
            to_state=current_state,
            event=event,
            actor=actor_model,
            actor_roles=actor.roles,
            guard_passed=False,
            reason=str(e),
            payload={"data": payload}
        )
        raise

    # 7. Return result
    return {
        "action": "transition",
        "instance_id": instance_id,
        "entity": entity,
        "from_state": from_state,
        "to_state": to_state,
        "event": event,
        "payload": payload
    }