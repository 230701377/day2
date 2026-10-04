from enum import Enum


class Role(str, Enum):
    REQUESTER = "requester"
    LEGAL = "legal"
    FINANCE = "finance"
    MANAGER = "manager"
    COMPLIANCE = "compliance"
    EXECUTIVE = "executive"
    ADMIN = "admin"


ALL_ROLES = [r.value for r in Role]


ROLE_SCOPES = {
    Role.REQUESTER: ["contract:create", "contract:read:own", "contract:update:own",
                     "approval:read:own", "approval:act:own", "obligation:read:own"],
    Role.LEGAL: ["contract:read:all", "contract:review", "clause:write",
                 "risk:write", "approval:act:legal", "approval:read:all",
                 "obligation:read:all", "audit:read"],
    Role.FINANCE: ["contract:read:all", "approval:act:finance",
                   "approval:read:all", "obligation:read:all", "audit:read"],
    Role.MANAGER: ["contract:read:all", "approval:act:manager",
                   "approval:read:all", "obligation:read:all"],
    Role.COMPLIANCE: ["contract:read:all", "approval:act:compliance",
                      "approval:read:all", "obligation:read:all",
                      "audit:read", "clause:validate"],
    Role.EXECUTIVE: ["contract:read:all", "approval:act:executive",
                     "approval:read:all", "obligation:read:all",
                     "audit:read", "analytics:read"],
    Role.ADMIN: ["*"],
}


def has_scope(role: Role, scope: str) -> bool:
    scopes = ROLE_SCOPES.get(role, [])
    if "*" in scopes:
        return True
    if scope in scopes:
        return True
    for s in scopes:
        if s.endswith(":*") and scope.startswith(s[:-1]):
            return True
    return False
