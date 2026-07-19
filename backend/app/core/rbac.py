"""
RBAC helpers.

Provides dependency factories that allow only certaain `User.role` values.
Roles : owner > admin > member > viewer (plus `is_superuser` always wins).

"""
from collections.abc import Callable
from fastapi import Depends, HTTPException, status

from app.deps import get_current_user

_ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}

def _rank(role: str) -> int: 
    return _ROLE_RANK.get(role, -1)

def require_roles (*allowed: str) -> Callable:
    """Allow only users whose role is in `allowed (or who are superusers)."""

    async def _dep(current_user=Depends(get_current_user)): 
        if getattr(current_user, "is_superuser", False):
            return current_user 
        if getattr(current_user, "role", None) in allowed: 
            return current_user 
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Requires one of roles: {', '.join(allowed)}",
        )
    return _dep

def require_min_role(min_role: str) -> Callable:
    """Allow only users whose role rank is >= `min_role".""" 
    threshold= _rank(min_role)

    async def _dep(current_user=Depends(get_current_user)):
        if getattr(current_user, "is_superuser", False): 
            return current_user 
        user_role=getattr(current_user, "role", "viewer") 
        if _rank(user_role) >= threshold:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role >= {min_role} (have {user_role})",
        )
    
    return _dep