from django.contrib import admin
from .models import Actor, Company, Tenant, TenantModel, WorkflowInstance, EntityDefinition, EntityInstance, TransitionLog, EntityRelationship, TenantUser, TenantRoleAssignment
from .roles import TENANT_ROLES
from django import forms

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("company_id", "name", "created_at")
    search_fields = ("company_id", "name")
    ordering = ("company_id",)
    readonly_fields = ("company_id", "created_at",)

    fieldsets = (
        ("Company Information", {
            "fields": ("name",)
        }),
        ("Metadata", {
            "fields": ("company_id", "created_at"),
        }),
    )


class TenantRoleAssignmentInline(admin.TabularInline):
    """
    Allows editing roles directly inside the TenantUser admin page.
    """
    model = TenantRoleAssignment
    extra = 1
    min_num = 0
    verbose_name = "Assigned Role"
    verbose_name_plural = "Assigned Roles"

@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ("tenant_name", "user", "role_list", "is_active", "joined_at", "invited_at")
    list_filter = ("tenant", "is_active")
    search_fields = ("tenant__name", "user__email", "user__username")
    ordering = ("tenant__name", "user__email")

    inlines = [TenantRoleAssignmentInline]

    fieldsets = (
        ("Tenant Membership", {
            "fields": ("tenant", "user", "is_active")
        }),
        ("Timestamps", {
            "fields": ("invited_at", "joined_at"),
            "classes": ("collapse",)
        }),
    )

    readonly_fields = ("invited_at", "joined_at")

    def tenant_name(self, obj):
        return obj.tenant.name
    tenant_name.short_description = "Tenant"

    def role_list(self, obj):
        return ", ".join(r.role for r in obj.roles.all())
    role_list.short_description = "Roles"


@admin.register(TenantRoleAssignment)
class TenantRoleAssignmentAdmin(admin.ModelAdmin):
    """
    Admin UI for role assignments.
    Useful for bulk editing or auditing.
    """
    list_display = ("tenant_user", "role", "assigned_at", "assigned_by")
    list_filter = ("role", "tenant_user__tenant_id")
    search_fields = (
        "tenant_user__tenant_id",
        "tenant_user__user__email",
        "tenant_user__user__username",
        "role",
    )
    ordering = ("tenant_user__tenant_id", "role")

    fieldsets = (
        ("Role Assignment", {
            "fields": ("tenant_user", "role")
        }),
        ("Metadata", {
            "fields": ("assigned_by", "assigned_at"),
            "classes": ("collapse",)
        }),
    )

    readonly_fields = ("assigned_at",)

@admin.register(TenantModel)
class TenantModelAdmin(admin.ModelAdmin):
    list_display = ('tenant_id','model_id','version','status','updated_at')
    search_fields = ('tenant_id','model_id','version','status')

@admin.register(EntityDefinition)
class EntityDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "version", "tenant_model", "is_active", "updated_at")
    list_filter = ("tenant_model", "is_active", "category")
    search_fields = ("name", "display_name", "description")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Info", {
            "fields": ("tenant_model", "name", "display_name", "description", "category", "icon")
        }),
        ("Schema", {
            "fields": ("version", "schema_json"),
        }),
        ("Workflow", {
            "fields": ("workflow_template",),
        }),
        ("Metadata", {
            "fields": ("is_active", "created_by", "created_at", "updated_at"),
        }),
    )


@admin.register(EntityInstance)
class EntityInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "entity_type", "tenant_model", "state", "created_at")
    list_filter = ("tenant_model", "entity_type", "state")
    search_fields = ("id", "entity_type__name")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Entity Info", {
            "fields": ("tenant_model", "entity_type", "version", "state")
        }),
        ("Data", {
            "fields": ("data",),
        }),
        ("Metadata", {
            "fields": ("actor", "created_at", "updated_at"),
        }),
    )

@admin.register(WorkflowInstance)
class WorkflowInstanceAdmin(admin.ModelAdmin):
    list_display = ('tenant_model','workflow_name','instance_id','state','updated_at')
    search_fields = ('tenant_model','workflow_name','instance_id','state')

@admin.register(TransitionLog)
class TransitionLogAdmin(admin.ModelAdmin):
    list_display = ("instance", "event", "from_state", "to_state", "actor_id", "created_at")
    list_filter = ("event", "from_state", "to_state")
    search_fields = ("instance__instance_id", "event", "actor_id")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Transition Info", {
            "fields": ("instance", "event", "from_state", "to_state")
        }),
        ("Actor Info", {
            "fields": ("actor_id", "actor_roles", "guard_passed", "reason")
        }),
        ("Payload", {
            "fields": ("payload",),
        }),
        ("Timestamp", {
            "fields": ("created_at",),
        }),
    )

@admin.register(EntityRelationship)
class EntityRelationshipAdmin(admin.ModelAdmin):
    list_display = ("relationship_id", "from_entity", "to_entity", "relationship_type")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("tenant_id", "name", "company_name", "created_at")
    search_fields = ("tenant_id", "name",  "company_name")

    def company_name(self, obj):
        return obj.company.name

    company_name.short_description = "Company"

class TransitionLogInline(admin.TabularInline):
    model = TransitionLog
    extra = 0
    fields = (
        "instance",
        "from_state",
        "to_state",
        "event",
        "guard_passed",
        "created_at",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True

# add custom form to handle roles as list
class ActorAdminForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(
        choices=TENANT_ROLES,
        widget=forms.CheckboxSelectMultiple,   # or forms.SelectMultiple
        required=False
    )

    class Meta:
        model = Actor
        fields = "__all__"

    def clean_roles(self):
        # Convert list → JSON list
        return self.cleaned_data["roles"]

@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    form = ActorAdminForm
    list_display = (
        "display_name",
        "actor_type",
        "identifier",
        "user",
        "created_at",
    )

    list_filter = ("actor_type", "created_at")
    search_fields = ("display_name", "identifier", "user__username", "user__email")
    readonly_fields = ("created_at",)

    inlines = [TransitionLogInline]

    fieldsets = (
        ("Actor Identity", {
            "fields": ("actor_type", "identifier", "display_name", "user")
        }),
        ("Roles & Metadata", {
            "fields": ("roles",)
        }),
        ("Timestamps", {
            "fields": ("created_at",),
        }),
    )