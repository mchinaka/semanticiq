from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from django.template.loader import get_template
from django.shortcuts import render
from .models import TenantUser, Tenant, TenantRoleAssignment
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from .roles import (
    TENANT_ROLE_ADMIN,
    TENANT_ROLE_DEVELOPER,
    TENANT_ROLE_RUNTIME,)

@require_GET
def index(request):
    return render(request, 'core/index.html')

def sentinel_os(request):
    return render(request, 'core/sentinel_os.html')

@require_GET
def main_menu(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("login")

    # All tenant memberships for this user
    memberships = (
        TenantUser.objects
        .filter(user=user)
        .select_related("tenant")
    )

    # User belongs to no tenants
    if not memberships.exists():
        return render(request, "core/no_access.html")

    # User belongs to exactly one tenant → auto-select it
    if memberships.count() == 1:
        tuser = memberships.first()
        tenant = tuser.tenant
        available_tenants = [tenant]

    # User belongs to multiple tenants → show switcher
    else:
        available_tenants = [m.tenant for m in memberships]

        # Determine which tenant is currently selected
        selected_id = request.GET.get("tenant_id")

        if selected_id:
            tenant = next((t for t in available_tenants if str(t.id) == selected_id), None)
        else:
            tenant = available_tenants[0]

        if tenant is None:
            return render(request, "core/no_access.html")

        tuser = memberships.filter(tenant=tenant).first()

    # Fetch roles
    roles = set(tuser.roles.values_list("role", flat=True))

    context = {
        "is_admin": TENANT_ROLE_ADMIN in roles,
        "is_developer": TENANT_ROLE_DEVELOPER in roles,
        "is_runtime": TENANT_ROLE_RUNTIME in roles,
        "roles": roles,

        # Pass the selected tenant
        "tenant": tenant,

        # Pass full tenant objects for the switcher
        "available_tenants": available_tenants,
    }

    return render(request, "core/main_menu.html", context)

@require_POST
def switch_tenant(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("login")

    selected_id = request.POST.get("tenant_id")

    if not selected_id:
        return render(request, "core/no_access.html")

    # Fetch tenant by tenant_id or name (your choice)
    try:
        tenant = Tenant.objects.get(tenant_id=selected_id)
    except Tenant.DoesNotExist:
        return render(request, "core/no_access.html")

    # Validate membership
    if not TenantUser.objects.filter(user=user, tenant=tenant).exists():
        return render(request, "core/no_access.html")

    # Store tenant in session
    request.session["tenant_id"] = tenant.tenant_id

    # Redirect to your main module entry point
    return redirect("main_menu")

