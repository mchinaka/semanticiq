def humanize_name(name: str | None) -> str:
    if not name:
        return ""
    import re
    return re.sub(r"([A-Z])", r" \1", name).strip()

def answer_knowledge_question(model_json: dict, message: str, intent: dict) -> str:
    """
    Knowledge responder:
    - If entity is known: describe it + list fields + required fields.
    - If no entity: give a general hint about what the model supports.
    """

    # -------------------------
    # Normalize entities (list → dict)
    # -------------------------
    raw_entities = model_json.get("entities", [])

    if isinstance(raw_entities, list):
        entities = {e.get("id"): e for e in raw_entities if e.get("id")}
    else:
        entities = raw_entities or {}

    entity_name = intent.get("entity")

    # -------------------------
    # Specific entity answer
    # -------------------------
    if entity_name and entity_name in entities:
        entity_def = entities[entity_name]
        h_entity = humanize_name(entity_name)

        fields = entity_def.get("fields", {}) or {}
        required_fields = [
            fname for fname, fdef in fields.items()
            if fdef.get("required")
        ]

        lines = []
        lines.append(f"**{h_entity}** is one of the workflow entities in this tenant.")

        # Fields
        if fields:
            lines.append("")
            lines.append("It has the following fields:")
            for fname, fdef in fields.items():
                h_field = humanize_name(fname)
                req = " (required)" if fdef.get("required") else ""
                lines.append(f"- **{h_field}**{req}")

        # Required fields
        if required_fields:
            lines.append("")
            lines.append("Required fields are:")
            for fname in required_fields:
                h_field = humanize_name(fname)
                lines.append(f"- **{h_field}**")

        # Workflow states (optional)
        states = entity_def.get("states") or entity_def.get("workflow_states")
        if states:
            lines.append("")
            lines.append("Typical workflow states include:")
            for s in states:
                lines.append(f"- **{humanize_name(s)}**")

        lines.append("")
        lines.append("You can ask me to create or update this workflow anytime.")

        return "\n".join(lines)

    # -------------------------
    # No specific entity → general model help
    # -------------------------
    if entities:
        lines = []
        lines.append("This tenant model defines the following workflow entities:")
        for ename in entities.keys():
            lines.append(f"- **{humanize_name(ename)}**")

        lines.append("")
        lines.append("You can ask things like:")
        lines.append("- *What is a Purchase Order*")
        lines.append("- *What fields does Supplier have*")
        lines.append("- *How does the approval workflow work*")

        return "\n".join(lines)

    # -------------------------
    # No entities at all
    # -------------------------
    return "I couldn't find any entities in this model yet. It may not be fully configured."