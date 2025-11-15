"""
Enterprise features for Metamorphic Guard.

Provides SSO, RBAC, and enhanced audit logging capabilities for enterprise deployments.
"""

from .auth import AuthenticationProvider, SSOProvider, authenticate_user
from .rbac import Role, Permission, RBACManager, check_permission
from .audit_enterprise import EnterpriseAuditLogger, AuditEvent

__all__ = [
    "AuthenticationProvider",
    "SSOProvider",
    "authenticate_user",
    "Role",
    "Permission",
    "RBACManager",
    "check_permission",
    "EnterpriseAuditLogger",
    "AuditEvent",
]

