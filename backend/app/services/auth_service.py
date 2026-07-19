import uuid

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)

from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.user import TokenResponse, UserCreate, UserResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db=db

    async def register(self, payload: UserCreate) -> User:
        result = await self.db.execute(select(User).where(User.email == payload.email))
        if result.scalar_one_or_none():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        
        first_name = (payload.full_name.split() or ["My"])[0]
        ws_name = f"{first_name}'s Workspace"
        ws_slug = await self._unique_workspace_slug(slugify(ws_name) or "workspace")
        workspace=Workspace(
            id=str(uuid.uuid4()),
            name=ws_name,
            slug=ws_slug,
            description="Auto-created on registration.", 
            workspace_type="product",
        )
        self.db.add(workspace)
        await self.db.flush()

        user = User(
            id=str(uuid.uuid4()),
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            is_active=True, 
            is_verified=False,
            workspace_id=workspace.id, 
            role="owner",
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def _unique_workspace_slug(self, base: str) -> str:
        slug=base
        counter = 1
        while True:
            result = await self.db.execute(
                select(Workspace).where(Workspace.slug == slug)
            )
            if not result.scalar_one_or_none():
                return slug
            slug =f"{base}-{counter}"
            counter += 1

    async def login(self, email: str, password: str) -> TokenResponse | None:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        access_token = create_access_token(user.id)
        refresh_token =  create_refresh_token(user.id)
        return TokenResponse (
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse | None: 
        payload = verify_refresh_token(refresh_token)
        if payload is None:
            return None
        user_id: str = payload["sub"]

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None

        access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)

        return TokenResponse (
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
    
    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()