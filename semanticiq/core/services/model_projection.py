from ..models import EntityDefinition, EntityRelationship, TenantModel
from django.db import transaction


@transaction.atomic
def project_model_to_entities(tenant_model: TenantModel):
    """
    Regenerates EntityDefinition + EntityRelationship rows
    from the JSON model stored in TenantModel.json_data.
    """

    data = tenant_model.json_data or {}
    entities = data.get("entities", [])

    # ---------------------------------------------------------
    # 1. Clear old projections for this model version
    # ---------------------------------------------------------
    EntityDefinition.objects.filter(tenant_model=tenant_model).delete()
    EntityRelationship.objects.filter(tenant_model=tenant_model).delete()

    definitions_to_create = []
    relationships_to_create = []

    # ---------------------------------------------------------
    # 2. Build EntityDefinition objects
    # ---------------------------------------------------------
    for ent in entities:
        name = ent.get("id")
        if not name:
            continue  # skip invalid entity

        display_name = ent.get("label", name)

        schema_json = {
            "attributes": ent.get("attributes", []),
            "rules": ent.get("rules", []),
            "views": ent.get("views", []),
            "workflow": ent.get("workflow", {}),
        }

        definitions_to_create.append(
            EntityDefinition(
                tenant_model=tenant_model,
                name=name,
                display_name=display_name,
                schema_json=schema_json,
                version=tenant_model.version,  # aligns with model versioning
            )
        )

    # Bulk insert definitions
    EntityDefinition.objects.bulk_create(definitions_to_create)

    # ---------------------------------------------------------
    # 3. Build lookup map: entity_name → EntityDefinition instance
    # ---------------------------------------------------------
    definitions = {
        d.name: d
        for d in EntityDefinition.objects.filter(tenant_model=tenant_model)
    }

    # ---------------------------------------------------------
    # 4. Build EntityRelationship objects
    # ---------------------------------------------------------
    for ent in entities:
        name = ent.get("id")
        if not name:
            continue

        for r in ent.get("relationships", []):
            from_name = r.get("from", name)
            to_name = r.get("to")

            # Validate relationship endpoints
            from_def = definitions.get(from_name)
            to_def = definitions.get(to_name)

            if not from_def or not to_def:
                continue  # skip invalid relationships

            relationships_to_create.append(
                EntityRelationship(
                    tenant_model=tenant_model,
                    relationship_id=r.get("id"),
                    from_entity=from_def,
                    to_entity=to_def,
                    relationship_type=r.get("type"),
                    cardinality=r.get("cardinality"),
                    key_mapping=r.get("keyMapping", {}),
                )
            )

    # Bulk insert relationships
    EntityRelationship.objects.bulk_create(relationships_to_create)
        