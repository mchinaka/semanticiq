import uuid
from django.db import models
from django.contrib.auth import get_user_model
from .roles import TENANT_ROLES

User = get_user_model() 

class Actor(models.Model):
    class ActorType(models.TextChoices):
        USER = "user", "Human User"
        SYSTEM = "system", "System Process"
        INTEGRATION = "integration", "External Integration"
        BOT = "bot", "Automation Bot"
        SCHEDULED = "scheduled", "Scheduled Job"

    actor_type = models.CharField(max_length=32, choices=ActorType.choices)

    # Unique identifier for the actor
    # For users: username or user.id
    # For systems: service name
    # For integrations: API client name
    identifier = models.CharField(max_length=128)

    # Human-readable name
    display_name = models.CharField(max_length=128)

    # Roles at the time of the transition
    roles = models.JSONField(default=list)

    # Optional link to Django User (for human actors)
    user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actors",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.display_name} ({self.actor_type})" 

class Company(models.Model):
    company_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=128)
    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="companies")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Tenant(models.Model):
    tenant_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=128)    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tenants")  # if you add companies later
    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="tenants")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantUser(models.Model):
    """
    A user belonging to a specific tenant.
    One Django user may belong to multiple tenants.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="users", blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenant_memberships")

    # Optional metadata
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("tenant", "user")

    def __str__(self):
        return f"{self.user.email} @ {self.tenant_id}"
    
    def has_role(self, role: str) -> bool:
        return self.roles.filter(role=role).exists()

    def is_admin(self):
        return self.has_role("admin")

    def is_developer(self):
        return self.has_role("developer")

    def is_runtime_user(self):
        return self.has_role("runtime")

    def is_auditor(self):
        return self.has_role("auditor")

    def is_support(self):
        return self.has_role("support")
    

class TenantRoleAssignment(models.Model):
    """
    Assigns one or more roles to a user within a tenant.
    """
    tenant_user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name="roles"
    )

    role = models.CharField(max_length=32, choices=TENANT_ROLES)

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        unique_together = ("tenant_user", "role")

    def __str__(self):
        return f"{self.tenant_user} → {self.role}"
       

class TenantModel(models.Model):    
    model_id = models.CharField(max_length=128)  # this more flexible ID allows user-defined model names
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="models", blank=True, null=True)
    version = models.CharField(max_length=32, default='draft')
    status = models.CharField(max_length=16, default='draft')
    json_data = models.JSONField()
    created_by = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=200, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_models")    

    class Meta:
        unique_together = ('tenant_id', 'model_id', 'version')

class EntityDefinition(models.Model):
    """
    Defines a dynamic entity type (e.g., PurchaseOrder, Invoice, Vendor).
    Includes versioning and JSON schema for dynamic fields.
    """
    tenant_model = models.ForeignKey(TenantModel, on_delete=models.CASCADE, related_name="entity_definitions", blank=True, null=True)

    name = models.CharField(max_length=128)             # internal name
    display_name = models.CharField(max_length=128)     # UI-friendly name
    description = models.TextField(blank=True)

    version = models.CharField(max_length=32, default="draft")            # schema version
    schema_json = models.JSONField()                    # dynamic form schema

    icon = models.CharField(max_length=64, blank=True)  # optional UI metadata
    category = models.CharField(max_length=64, blank=True)

    workflow_template = models.CharField(
        max_length=128, blank=True, null=True
    )  # name/id of default workflow

    is_active = models.BooleanField(default=True)

    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="entity_definitions")   
    created_by = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=200, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tenant_model", "name", "version")

    def __str__(self):
        return f"{self.name} (v{self.version})"


class EntityInstance(models.Model):
    """
    Stores actual records created from an EntityDefinition.
    Example: a specific PurchaseOrder instance.
    """
    id = models.AutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, null=True, blank=True)  # public identifier
    tenant_model = models.ForeignKey(TenantModel, on_delete=models.CASCADE, related_name="entity_instances", blank=True, null=True)
    entity_type = models.CharField(max_length=200, null=True)  # name of the EntityDefinition
    version = models.IntegerField(null=True)  # which schema version was used

    data = models.JSONField(default=dict)   # actual field values
    state = models.CharField(max_length=64, default="Draft")
     
    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="entity_instances") 
    
    created_by = models.CharField(max_length=200, null=True)   # business creator
    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.CharField(max_length=200, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_model", "entity_type"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        return f"{self.entity_type} #{self.id}"


class WorkflowInstance(models.Model):    
    tenant_model = models.ForeignKey(TenantModel, on_delete=models.CASCADE, related_name="workflows", blank=True, null=True)
    model_version = models.CharField(max_length=32, null=True, blank=True)    # NEW: version for traceability
    entity = models.CharField(max_length=128, null=True, blank=True)          # NEW: entity name
    workflow_name = models.CharField(max_length=128)
    instance_id = models.CharField(max_length=64, unique=True)  # make unique for safe lookups
    state = models.CharField(max_length=64)
    payload = models.JSONField()
    created_by = models.CharField(max_length=200, null=True)   # business creator
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=200, null=True)
    updated_at = models.DateTimeField(auto_now=True)    
    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="workflows")
    roles = models.JSONField(default=list)             # NEW: actor roles
    entity_instance = models.ForeignKey(
        EntityInstance,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workflows"
    )


class TransitionLog(models.Model):
    """
    Audit trail for transitions.
    """
    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name="logs")
    from_state = models.CharField(max_length=128)
    to_state = models.CharField(max_length=128)
    event = models.CharField(max_length=128)    
    actor = models.ForeignKey(Actor, on_delete=models.SET_NULL, null=True, blank=True, related_name="transitions")
    actor_roles = models.JSONField(default=list)  # NEW: roles of the actor
    guard_passed = models.BooleanField(default=True)
    reason = models.TextField(blank=True)  # failure reason or notes
    payload = models.JSONField(default=dict)  # any extra data sent with signal
    created_by = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["instance", "created_at"]),
            models.Index(fields=["event"]),
        ]


class EntityRelationship(models.Model):
    tenant_model = models.ForeignKey(TenantModel, on_delete=models.CASCADE, related_name="relationships", blank=True, null=True)

    from_entity = models.ForeignKey(
        EntityDefinition,
        on_delete=models.CASCADE,
        related_name="outgoing_relationships",
        null=True,
        blank=True
    )
    to_entity = models.ForeignKey(
        EntityDefinition,
        on_delete=models.CASCADE,
        related_name="incoming_relationships",
        null=True,
        blank=True
    )

    relationship_id = models.CharField(max_length=128, null=True, blank=True)
    relationship_type = models.CharField(max_length=64, null=True, blank=True)
    cardinality = models.CharField(max_length=64, null=True, blank=True)
    key_mapping = models.JSONField(default=dict) 

class SignupRequest(models.Model):
    email = models.EmailField()
    company_name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company_name} ({self.email})"


