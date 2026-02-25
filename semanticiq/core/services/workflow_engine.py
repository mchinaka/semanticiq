# -*- coding: utf-8 -*-
import uuid
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
from ..models import Actor as ActorModel

from .rule_eval import eval_expr


class WorkflowError(Exception):
    pass


@dataclass
class EngineActor:
    user_id: str
    roles: List[str]

    @classmethod
    def from_model(cls, actor: ActorModel):
        return cls(
            user_id=actor.identifier,
            roles=actor.roles or []
        )
    
def get_actor_for_user(user):
    try:
        return ActorModel.objects.get(user=user)
    except ActorModel.DoesNotExist:
        return None

class WorkflowEngine:
    """
    Lightweight workflow engine that works with current model shape:
      model = {
        "entities": [
          {
            "id": "PurchaseOrder",
            "workflow": {
              "initial": "Draft",                 # optional
              "states": [{"id": "Draft"}, {"id": "Submitted"}, {"id":"Approved"}],
              "transitions": [
                 {"from":"Draft","to":"Submitted","event":"submit","guard":{"expr":"ctx['amount'] <= 5000"},"actions":[...]},
                 {"from":"Submitted","to":"Approved","event":"approve"}
              ]
            }
          },
          ...
        ]
      }
    """

    def __init__(self, model_json: Any):
        self.model = self._normalize_model(model_json)

    # ------------------------- Normalization -------------------------

    @staticmethod
    def _normalize_model(model_json: Any) -> Dict[str, Any]:
        """Accept dict | list | str, return dict. Prefer an object with 'entities'."""
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

    def _entities_list(self) -> List[Dict[str, Any]]:
        ents = self.model.get("entities") or []
        if isinstance(ents, list):
            return [e for e in ents if isinstance(e, dict)]
        if isinstance(ents, dict):
            # If you ever switch to dict form: {"PurchaseOrder": {...}}
            return [{"id": k, **(v if isinstance(v, dict) else {})} for k, v in ents.items()]
        return []

    def _find_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        for e in self._entities_list():
            if str(e.get("id")) == str(entity_id):
                return e
        return None

    def _find_workflow(self, entity_id: str) -> Dict[str, Any]:
        """
        Prefer entity['workflow']; fallback to top-level 'workflows'[entity_id] if present.
        """
        e = self._find_entity(entity_id)
        if e and isinstance(e.get("workflow"), dict):
            return e["workflow"]

        # Optional fallback if you later store workflows at top level
        wfs = self.model.get("workflows")
        if isinstance(wfs, dict) and isinstance(wfs.get(entity_id), dict):
            return wfs[entity_id]

        return {}

    # ------------------------- Introspection -------------------------

    def states(self, entity_id: str) -> List[str]:
        wf = self._find_workflow(entity_id)
        states = wf.get("states") or []
        out: List[str] = []
        for s in states:
            if isinstance(s, dict) and "id" in s:
                out.append(str(s["id"]))
            elif isinstance(s, str):
                out.append(s)
        if not out:
            # derive from transitions if states not provided
            seen = set()
            for t in wf.get("transitions") or []:
                if isinstance(t, dict):
                    if "from" in t:
                        seen.add(str(t["from"]))
                    if "to" in t:
                        seen.add(str(t["to"]))
            out = list(seen) if seen else ["Draft", "Terminal"]
        return out

    def initial_state(self, entity_id: Optional[str]) -> Optional[str]:
        if not entity_id:
            return None
        wf = self._find_workflow(entity_id)
        init = wf.get("initial")
        if isinstance(init, str) and init:
            return init
        # fallback: first state
        st = self.states(entity_id)
        return st[0] if st else "Draft"

    def transitions(self, entity_id: str) -> List[Dict[str, Any]]:
        wf = self._find_workflow(entity_id)
        trs = wf.get("transitions") or []
        return [t for t in trs if isinstance(t, dict)]

    # ------------------------- Runtime ops -------------------------

    def start(self, entity_id: str, payload: Dict[str, Any], actor: Optional[EngineActor] = None) -> Dict[str, Any]:
        wf = self._find_workflow(entity_id)
        if not wf:
            raise WorkflowError(f"No workflow for entity '{entity_id}'")

        start_state = self.initial_state(entity_id) or "Draft"
        instance_id = str(uuid.uuid4())
        instance = {
            "instanceId": instance_id,
            "state": start_state,
            "entity": entity_id,
            "payload": payload or {},
            "history": [
                {
                    "event": "start",
                    "actor": {"user_id": getattr(actor, "user_id", None), "roles": getattr(actor, "roles", [])} if actor else None,
                    "to": start_state,
                }
            ],
        }
        return instance

    def _from_matches(self, t_from: Union[str, List[str], None], current_state: str) -> bool:
        if t_from in (None, "", "*"):
            return True
        if isinstance(t_from, list):
            return current_state in [str(x) for x in t_from]
        return str(t_from) == str(current_state)

    def _event_matches(self, t: Dict[str, Any], event: Optional[str]) -> bool:
        if event is None:
            # If caller didn't specify an event, allow transitions without event or any event (legacy next())
            return True
        ev = t.get("event") or t.get("on")
        return ev == event

    def _guard_allows(self, t: Dict[str, Any], context: Dict[str, Any]) -> bool:
        guard = (t.get("guard") or {}).get("expr")
        if not guard:
            return True
        try:
            # By convention, pass the payload/context into eval_expr
            return bool(eval_expr(guard, context))
        except Exception:
            # Guard errors -> treat as False for safety
            return False

    def next(self, entity_id: str, current_state: str, payload: Dict[str, Any], event: Optional[str] = None) -> Dict[str, Any]:
        """ Compute the next state (pure function style). Does not mutate an instance.
        - Respects 'from', optional 'event'/'on', 'guard'. Returns first matching transition.
        - Falls back to staying in current_state if nothing applies.
        Return: {"state": <new_state>, "actions": [ ... ], "transition": { ... }?}"""

        wf = self._find_workflow(entity_id)
        if not wf:
            raise WorkflowError(f"No workflow for entity '{entity_id}'")

        transitions = self.transitions(entity_id)

            # Build guard evaluation context
            # ---------------------------------------------------------
            #  This adds actor + payload into a unified context.
            # ---------------------------------------------------------
        context = {}

        # Include payload fields at top level
        if payload:
            context.update(payload)

        # Include actor info if the engine has it
        if hasattr(self, "actor") and self.actor:
            context["actor"] = {
                "identifier": getattr(self.actor, "identifier", None),
                "user_id": getattr(self.actor, "user_id", None),
                "username": getattr(self.actor, "username", None),
                "roles": getattr(self.actor, "roles", []),
                }

            # Debug print
        print("GUARD CONTEXT:", context)

        # Evaluate transitions
        for t in transitions:
            if not self._from_matches(t.get("from"), current_state):
                continue
            if not self._event_matches(t, event):
                continue
            if not self._guard_allows(t, context):   
                continue

            return {
            "state": t.get("to", current_state),
            "actions": t.get("actions", []),
            "transition": t,
        }

        # No match -> no-op
        return {"state": current_state, "actions": [], "transition": None}

    def apply_signal(
        self,
        instance: Dict[str, Any],
        event: str,
        actor: Optional[EngineActor] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Mutate an existing instance in-place based on a signal/event.
        - Merges `payload` into instance['payload'].
        - Appends a history entry.
        """
        entity_id = instance.get("entity")
        if not entity_id:
            raise WorkflowError("Instance missing 'entity'")

        current_state = instance.get("state")
        if current_state is None:
            # If instance was created externally, derive an initial state
            current_state = self.initial_state(entity_id) or "Draft"
            instance["state"] = current_state

        payload = payload or {}
        # Merge payload into instance payload
        instance_payload = instance.setdefault("payload", {})
        try:
            instance_payload.update(payload)
        except Exception:
            # if not a dict, replace
            instance["payload"] = payload

        # Compute next state
        nx = self.next(entity_id, current_state, instance.get("payload") or {}, event)
        new_state = nx["state"]

        # Append history
        history = instance.setdefault("history", [])
        history.append(
            {
                "event": event,
                "actor": {"user_id": getattr(actor, "user_id", None), "roles": getattr(actor, "roles", [])} if actor else None,
                "from": current_state,
                "to": new_state,
                "actions": nx.get("actions", []),
            }
        )

        # Update state
        instance["state"] = new_state
        return instance
