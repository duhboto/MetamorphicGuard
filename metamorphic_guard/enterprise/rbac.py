"""
Role-Based Access Control (RBAC) for enterprise deployments.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Set

from ..types import JSONDict


class Permission(Enum):
    """Permissions for accessing Metamorphic Guard features."""

    # Evaluation permissions
    RUN_EVALUATION = "run_evaluation"
    VIEW_REPORTS = "view_reports"
    EXPORT_REPORTS = "export_reports"

    # Configuration permissions
    MANAGE_POLICIES = "manage_policies"
    MANAGE_PLUGINS = "manage_plugins"
    CONFIGURE_SYSTEM = "configure_system"

    # Data permissions
    VIEW_AUDIT_LOGS = "view_audit_logs"
    DELETE_DATA = "delete_data"
    EXPORT_DATA = "export_data"

    # Administrative permissions
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    SYSTEM_ADMIN = "system_admin"


class Role:
    """Role definition with associated permissions."""

    def __init__(self, name: str, permissions: Set[Permission]) -> None:
        """
        Initialize role.

        Args:
            name: Role name
            permissions: Set of permissions granted to this role
        """
        self.name = name
        self.permissions = permissions

    def has_permission(self, permission: Permission) -> bool:
        """Check if role has a specific permission."""
        return permission in self.permissions

    def to_dict(self) -> JSONDict:
        """Convert role to dictionary."""
        return {
            "name": self.name,
            "permissions": [p.value for p in self.permissions],
        }


class RBACManager:
    """Manager for role-based access control."""

    # Built-in roles
    ADMIN = Role(
        "admin",
        {
            Permission.RUN_EVALUATION,
            Permission.VIEW_REPORTS,
            Permission.EXPORT_REPORTS,
            Permission.MANAGE_POLICIES,
            Permission.MANAGE_PLUGINS,
            Permission.CONFIGURE_SYSTEM,
            Permission.VIEW_AUDIT_LOGS,
            Permission.DELETE_DATA,
            Permission.EXPORT_DATA,
            Permission.MANAGE_USERS,
            Permission.MANAGE_ROLES,
            Permission.SYSTEM_ADMIN,
        },
    )

    ANALYST = Role(
        "analyst",
        {
            Permission.RUN_EVALUATION,
            Permission.VIEW_REPORTS,
            Permission.EXPORT_REPORTS,
            Permission.VIEW_AUDIT_LOGS,
        },
    )

    VIEWER = Role(
        "viewer",
        {
            Permission.VIEW_REPORTS,
        },
    )

    def __init__(self) -> None:
        """Initialize RBAC manager with default roles."""
        self.roles: Dict[str, Role] = {
            "admin": self.ADMIN,
            "analyst": self.ANALYST,
            "viewer": self.VIEWER,
        }
        self.user_roles: Dict[str, List[str]] = {}

    def add_role(self, role: Role) -> None:
        """Add a custom role."""
        self.roles[role.name] = role

    def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign a role to a user."""
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' does not exist")
        if user_id not in self.user_roles:
            self.user_roles[user_id] = []
        if role_name not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role_name)

    def remove_role(self, user_id: str, role_name: str) -> None:
        """Remove a role from a user."""
        if user_id in self.user_roles:
            if role_name in self.user_roles[user_id]:
                self.user_roles[user_id].remove(role_name)

    def get_user_roles(self, user_id: str) -> List[Role]:
        """Get all roles for a user."""
        role_names = self.user_roles.get(user_id, [])
        return [self.roles[name] for name in role_names if name in self.roles]

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User identifier
            permission: Permission to check

        Returns:
            True if user has permission, False otherwise
        """
        user_roles = self.get_user_roles(user_id)
        return any(role.has_permission(permission) for role in user_roles)


def check_permission(
    rbac_manager: RBACManager,
    user_id: str,
    permission: Permission,
) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        rbac_manager: RBAC manager instance
        user_id: User identifier
        permission: Permission to check

    Returns:
        True if user has permission, False otherwise
    """
    return rbac_manager.check_permission(user_id, permission)

