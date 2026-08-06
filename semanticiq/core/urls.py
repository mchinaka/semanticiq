# semanticiq/core/urls.py
from django.urls import path

from semanticiq.core.services.model_factory import create_model_from_data, create_model_from_spreadsheet
from . import views_registry as reg
from . import views_runtime as rt
from . import views_general as gen
from . import views_auth as auth
from .views_studio import studio
from .views_chat import chat_endpoint
from .views_forms import form_schema, form_submit


urlpatterns = [

    # Authentication
    path('login', auth.login_view, name='login'),
    path('logout', auth.logout, name='logout'),
    path("signup", auth.signup_view, name="signup"),
    
    # General
    path('', gen.index, name='index'),
    path('sentinel-os', gen.sentinel_os, name='sentinel-os'),
    path('alchemy', gen.alchemy, name='alchemy'),
    path('main_menu', gen.main_menu, name='main_menu'),
    path('switch_tenant', gen.switch_tenant, name='switch_tenant'),
    
    # Studio
    path('studio', studio, name='studio'),

    # Registry
    path('api/templates', reg.list_templates),
    path('api/tenants/<str:tenantId>/models', reg.create_model), #create from template
    path("api/tenants/<str:tenantId>/list_models", reg.list_models),
    path('api/tenants/<str:tenantId>/models/<str:modelId>', reg.get_model),
    path('api/tenants/<str:tenantId>/models/<str:modelId>/update', reg.update_model),
    path("runtime/tenant-users", reg.tenant_users, name="tenant_users"),


    # Prompt templates & Buidlder
    path("api/prompt-templates", reg.list_prompt_templates),
    path("api/<str:tenantId>/models_from_prompt", reg.create_model_from_prompt),


    # Model creation from different sources
    path("api/tenants/<tenantId>/models/from-prompt", reg.create_model_from_prompt),
    path("api/tenants/<tenantId>/models/from-spreadsheet", create_model_from_spreadsheet),
    path("api/tenants/<tenantId>/models/from-data", create_model_from_data),

    # NEW: Validation + Patch
    path('api/tenants/<str:tenantId>/models/<str:modelId>/validate', reg.validate_draft),
    path('api/tenants/<str:tenantId>/models/<str:modelId>/patch', reg.patch_model),

    path('api/tenants/<str:tenantId>/models/<str:modelId>/publish', reg.publish_model),

    # Runtime
    path('api/<str:tenantId>/workflows/<str:name>/instances', rt.start_workflow),
    path('api/<str:tenantId>/workflows/<str:name>/instances/<str:instanceId>/signal', rt.signal_workflow),
    path('api/<str:tenantId>/workflows/<str:name>/instances/<str:instanceId>/state', rt.get_state),
    
    # Entities listing for dynamic forms and tranisitions (approval etc)
    path("runtime/entities", rt.list_entities, name="list_entities"),
    path("runtime/transition", rt.transition, name="transition"),
    
    # Phase 4 UI + endpoints
    path("runtime/", rt.runtime_page, name="runtime_page"),
    path("chat", chat_endpoint, name="chat_endpoint"),
    path("runtime/form-schema", form_schema, name="form_schema"),
    path("runtime/form-submit", form_submit, name="form_submit"),
    path("runtime/workflows", rt.list_workflows, name="list_workflows"),
    path("runtime/pending-approvals", rt.pending_approvals, name="pending_approvals"),
    path("runtime/workflow/<str:workflow_id>", rt.get_workflow, name="get_workflow"),
    
]
