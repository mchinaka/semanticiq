# semanticiq/core/management/commands/seed_mvp.py
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.apps import apps  # <-- use app registry

class Command(BaseCommand):
    help = "Seed a draft MVP model for a tenant from resources/templates/procurement.mvp.json"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant ID (e.g., tenantA)")
        parser.add_argument("--model-id", default="procurement-mvp")
        parser.add_argument("--model-version", dest="version", default="1.0.0",
                            help='Semantic version (default: "1.0.0")')

    def handle(self, *args, **opts):
        # Resolve AFTER apps are loaded to avoid NameError/circular import issues
        # If your app label is not "core", replace it with the label from apps.py
        RegistryModel = apps.get_model("core", "TenantModel")

        tenant = opts["tenant"]
        model_id = opts["model_id"]
        version = opts["version"]

        # Get the template path from settings
        resources_dir = getattr(settings, "RESOURCES_DIR", None)
        if not resources_dir:
            raise CommandError("settings.RESOURCES_DIR is not configured")

        seed_path = Path(resources_dir) / "templates" / "procurement.mvp.json"
        if not seed_path.exists():
            raise CommandError(f"Template not found: {seed_path}")

        # Load JSON and normalize root (object or single-element list)
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            raise CommandError(f"Failed to load template JSON: {e}")

        if isinstance(raw, dict):
            data = raw
        elif isinstance(raw, list):
            if not raw:
                raise CommandError("Template JSON is an empty list; nothing to seed.")
            data = raw[0]
            if not isinstance(data, dict):
                raise CommandError("First element in the template array is not an object.")
        else:
            raise CommandError(f"Unsupported template root type: {type(raw).__name__}")

        # Inject/override metadata
        data["tenant_id"] = tenant
        data["model_id"] = model_id
        # Your model uses version as a string (was 'draft' by default). We'll set a semantic value:
        data["version"] = version

        # Upsert draft row in your registry model (matches your fields)
        obj, created = RegistryModel.objects.update_or_create(
            tenant_id=tenant,
            model_id=model_id,
            version=version,
            defaults={"status": "draft", "json_data": data},
        )

        entities = data.get("entities")
        workflows = data.get("workflows")
        entities_count = len(entities) if isinstance(entities, dict) else 0
        workflows_count = len(workflows) if isinstance(workflows, dict) else 0

        self.stdout.write(self.style.SUCCESS(
            f'{"Created" if created else "Updated"} draft model '
            f'tenant={tenant}, modelId={model_id}, version={version}, '
            f'entities={entities_count}, workflows={workflows_count}'
        ))
