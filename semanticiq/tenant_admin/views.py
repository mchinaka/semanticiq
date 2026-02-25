from django.shortcuts import render, redirect, get_object_or_404
from ..core.models import TenantUser, TenantRoleAssignment, Tenant
from ..core.roles import TENANT_ROLES
from django.utils.crypto import get_random_string
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.urls import reverse
from ..core.services.email import send_welcome_email
import json


def get_tenant_context(request):
    user = request.user

    memberships = (
        TenantUser.objects
        .filter(user=user)
        .select_related("tenant")
    )

    if not memberships.exists():
        return None  # caller handles no-access

    # Determine selected tenant
    if memberships.count() == 1:
        tuser = memberships.first()
        tenant = tuser.tenant
        available_tenants = [tenant]
        request.session["tenant_id"] = tenant.tenant_id
    else:
        available_tenants = [m.tenant for m in memberships]

        selected_id = (
            request.GET.get("tenant_id")
            or request.session.get("tenant_id")
        )

        tenant = next(
            (t for t in available_tenants if str(t.tenant_id) == str(selected_id)),
            available_tenants[0]
        )

        request.session["tenant_id"] = tenant.tenant_id
        tuser = memberships.filter(tenant=tenant).first()

    # Extract assigned roles (actual values)
    assigned_roles = set(tuser.roles.values_list("role", flat=True))

    # Provide role value/label pairs for templates
    # TENANT_ROLES is already imported and looks like:
    # [("admin", "Administrator"), ("developer", "Developer"), ...]
    
    return {
        "tenant": tenant,
        "available_tenants": available_tenants,
        "roles": TENANT_ROLES,          # <-- value/label pairs for checkboxes
        "assigned_roles": assigned_roles,  # <-- actual assigned values
        "tuser": tuser,
    }

def tenant_user_list(request):
    ctx = get_tenant_context(request)
    if ctx is None:
        return render(request, "core/no_access.html")

    tenant = ctx["tenant"]

    users = (
        TenantUser.objects
        .filter(tenant=tenant)
        .select_related("user")
        .prefetch_related("roles")
    )

    # Add JSON role list for each user (required for the modal)    
    for u in users:
        roles = list(u.roles.values_list("role", flat=True))
        # Convert JSON to single-quoted JS array
        u.assigned_roles_json = json.dumps(roles)

    return render(request, "tenant_admin/list.html", {
        "users": users,
        **ctx
    })

def tenant_user_create(request):
    ctx = get_tenant_context(request)
    tenant = ctx["tenant"]

    if request.method == "POST":
        username = request.POST["username"].strip()
        first_name = request.POST["first_name"].strip()
        last_name = request.POST["last_name"].strip()
        email = request.POST["email"].strip().lower()
        roles = request.POST.getlist("roles")

        # Check if global user exists
        user = User.objects.filter(email=email).first()
        created_new_user = False

        if user:
            # Check if already in this tenant
            if TenantUser.objects.filter(tenant=tenant, user=user).exists():
                messages.error(request, "User already exists in this tenant.")
                return redirect("tenant_user_list")
        else:
            # Create new global user
            password = get_random_string(12)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            created_new_user = True

        # Create tenant membership
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            is_active=True,
        )

        # Assign roles
        for role in roles:
            TenantRoleAssignment.objects.create(
                tenant_user=tenant_user,
                role=role,
                assigned_by=request.user
            )

        # Send welcome email only for new global users
        if created_new_user:
            send_welcome_email(user, password)

        messages.success(request, f"User added to tenant.")
        return redirect("tenant_user_list")

def tenant_user_edit(request, pk):
    ctx = get_tenant_context(request)
    if ctx is None:
        return render(request, "core/no_access.html")

    tenant = ctx["tenant"]
    tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)
    user = tenant_user.user

    if request.method == "POST":

        # Update global user fields
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()
        user.save()

        # Update tenant-specific active flag
        tenant_user.is_active = "is_active" in request.POST
        tenant_user.save()

        # Update roles (tenant-scoped)
        new_roles = set(request.POST.getlist("roles"))
        old_roles = set(tenant_user.roles.values_list("role", flat=True))

        # Add new roles
        for role in new_roles - old_roles:
            TenantRoleAssignment.objects.create(
                tenant_user=tenant_user,
                role=role,
                assigned_by=request.user
            )

        # Remove roles that were unchecked
        TenantRoleAssignment.objects.filter(
            tenant_user=tenant_user,
            role__in=(old_roles - new_roles)
        ).delete()

        messages.success(request, "User updated successfully.")
        return redirect("tenant_user_list")

    # GET request → prepare JSON for modal
    assigned_roles = list(tenant_user.roles.values_list("role", flat=True))
    assigned_roles_json = json.dumps(assigned_roles)

    return render(request, "tenant_admin/edit.html", {
        "tenant_user": tenant_user,
        "roles": TENANT_ROLES,
        "assigned_roles": assigned_roles,
        "assigned_roles_json": assigned_roles_json,
        **ctx
    })

def tenant_user_delete(request, pk):
    ctx = get_tenant_context(request)
    if ctx is None:
        return render(request, "core/no_access.html")

    tenant = ctx["tenant"]
    tenant_user = get_object_or_404(TenantUser, pk=pk, tenant=tenant)

    # Delete only the tenant membership
    tenant_user.delete()

    messages.success(request, "User removed from tenant.")
    return redirect("tenant_user_list")