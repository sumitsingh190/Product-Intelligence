from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_access_token
from app.database import get_db

security= HTTPBearer()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    token = credentials.credentials
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token", 
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload",
        )
    return user_id

CurrentUserIdDep = Annotated[str, Depends (get_current_user_id)]

async def get_current_user(
    user_id: CurrentUserIdDep,
    db: SessionDep,
):
    from app.models.user import User 
    from sqlalchemy import select
    
    result = await db.execute(select(User).where(User.id == user_id))
    user=result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user", )

    return user

CurrentUserDep = Annotated[object, Depends (get_current_user)]

async def get_current_superuser (current_user=Depends(get_current_user)):

    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions",
        )
    return current_user

def ensure_workspace_access(user, workspace_id: str) -> None:
    """Raise 404 if the user cannot access this workspace.
    
    Uses 404 rather than 403 so we don't leak which workspace IDs exist. 
    Workspace is the sole tenant boundary a user sees only their own workspace unless they're a superuser.
    """
    if getattr(user, "is_superuser", False):
        return

    if getattr(user, "workspace_id", None) != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found", 
        )