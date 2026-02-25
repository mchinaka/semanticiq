from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET
from .models import TenantUser
from .roles import (
    TENANT_ROLE_ADMIN,
    TENANT_ROLE_DEVELOPER,
    TENANT_ROLE_RUNTIME,
)

@require_GET
def studio(request):
    user = request.user
    if not user.is_authenticated:
        return redirect("login")

    # Fetch all tenant memberships for this user
    memberships = (
        TenantUser.objects
        .filter(user=user)
        .select_related("tenant")
    )

    if not memberships.exists():
        return render(request, "core/no_access.html")

    # Determine selected tenant
    if memberships.count() == 1:
        # Auto-select the only tenant
        tuser = memberships.first()
        tenant = tuser.tenant
        available_tenants = [tenant]

        # Store in session for consistency
        request.session["tenant_id"] = tenant.tenant_id

    else:
        # User has multiple tenants
        available_tenants = [m.tenant for m in memberships]

        # Allow switching via ?tenant_id=... or session
        selected_id = request.GET.get("tenant_id") or request.session.get("tenant_id")

        # Pick tenant: selected → session → fallback to first
        tenant = next(
            (t for t in available_tenants if str(t.tenant_id) == str(selected_id)),
            available_tenants[0]
        )

        # Update session with the selected tenant
        request.session["tenant_id"] = tenant.tenant_id

        # Get the TenantUser record for this tenant
        tuser = memberships.filter(tenant=tenant).first()

    # Extract roles
    roles = set(tuser.roles.values_list("role", flat=True))

    context = {
        "is_admin": TENANT_ROLE_ADMIN in roles,
        "is_developer": TENANT_ROLE_DEVELOPER in roles,
        "is_runtime": TENANT_ROLE_RUNTIME in roles,
        "roles": roles,

        # Selected tenant
        "tenant": tenant,

        # All tenants for the switcher
        "available_tenants": available_tenants,
    }

    return render(request, "core/studio.html", context)