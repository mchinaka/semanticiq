# semanticiq/tenant_admin/admin_urls.py
from django.urls import path
from django.shortcuts import redirect
from .views import tenant_user_list, tenant_user_create, tenant_user_edit, tenant_user_delete

urlpatterns = [
    path("", lambda request: redirect("tenant_user_list")),
    path("users/", tenant_user_list, name="tenant_user_list"),
    path("users/create/", tenant_user_create, name="tenant_user_create"),
    path("users/<int:pk>/edit/", tenant_user_edit, name="tenant_user_edit"),
    path("users/<int:pk>/delete/", tenant_user_delete, name="tenant_user_delete"),
]