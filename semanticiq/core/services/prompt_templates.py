PROMPT_TEMPLATES = {
    "process_model": """
You are an expert system designer. Convert the user description into an ontology-lite JSON model.

STRICT RULES:
- Output ONLY valid JSON.
- Follow the exact schema below. Do not add or remove fields.
- Use "id" for internal identifiers and "label" for human-readable names.
- Every entity MUST include: id, label, attributes, relationships.
- Every attribute MUST include: id, type.
- relationships MUST be an array (can be empty).
- security MUST be an empty object {}.
- Do NOT include "name" fields anywhere.
- Do NOT include accessControl, roles, or permissions.
- Do NOT include explanations or comments.

USER DESCRIPTION:
{user_prompt}

REQUIRED OUTPUT SCHEMA:
{
  "modelId": "<model id>",
  "entities": [
    {
      "id": "EntityName",
      "label": "Entity Name",
      "attributes": [
        { "id": "attrName", "type": "string" }
      ],
      "relationships": []
    }
  ],
  "security": {}
}

RELATIONSHIP RULES:
- Every relationship MUST follow this exact schema:
  {
    "id": "relationshipId",
    "type": "references",
    "from": "SourceEntityId",
    "to": "TargetEntityId",
    "cardinality": "one-to-one" | "one-to-many" | "many-to-one" | "many-to-many"
  }
- "type" MUST always be "references".
- "from" MUST be the entity that owns the relationship.
- "to" MUST be the target entity id.
- "cardinality" MUST be included.
- Do NOT invent relationship types.
- Do NOT use the target entity name as the relationship type.
""",

    "master_data": """
You are an expert data modeler. Convert the following master data description
into an ontology-lite JSON model.

REQUIREMENTS:
- Identify the core entity.
- Identify attributes with types.
- Identify related entities and relationships.
- Identify lifecycle states if applicable.

USER DESCRIPTION:
{user_prompt}

OUTPUT FORMAT:
{ "entities": [...], "relationships": [...] }
""",

    "integration_flow": """
You are an expert integration architect. Convert the following data flow description
into an ontology-lite JSON model.

REQUIREMENTS:
- Identify source and target entities.
- Identify mapping rules.
- Identify transformation steps.
- Identify relationships between entities.

USER DESCRIPTION:
{user_prompt}

OUTPUT FORMAT:
{ "entities": [...], "relationships": [...], "mappings": [...] }
"""
}