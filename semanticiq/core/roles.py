# roles.py (recommended separate file)
TENANT_ROLE_ADMIN = "admin"
TENANT_ROLE_DEVELOPER = "developer"
TENANT_ROLE_RUNTIME = "runtime"
TENANT_ROLE_AUDITOR = "auditor"
TENANT_ROLE_SUPPORT = "support"

TENANT_ROLES = [
    (TENANT_ROLE_ADMIN, "Tenant Admin"),
    (TENANT_ROLE_DEVELOPER, "Developer"),
    (TENANT_ROLE_RUNTIME, "Runtime User"),
    (TENANT_ROLE_AUDITOR, "Auditor (Read-only)"),
    (TENANT_ROLE_SUPPORT, "Support Operator"),
]