from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.core.rate_limit import limiter
from app.deps import CurrentUserDep, SessionDep
from app.schemas.user import(
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLoginRequest,
    UserResponse,
)

from app.services.auth_service import AuthService

router=APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_auth)
async def register(request: Request, payload:UserCreate, db:SessionDep):
    service=AuthService(db)
    user=await service.register(payload)
    return user

@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_auth)
async def login(request: Request, payload: UserLoginRequest, db: SessionDep):
    service = AuthService(db)
    tokens = await service.login(payload.email, payload.password)
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return tokens

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_auth)
async def refresh_token(request: Request, payload: RefreshTokenRequest, db: SessionDep):
    service=AuthService(db)
    tokens = await service.refresh(payload.refresh_token)
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return tokens

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep):
    return current_user

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
#JWT logout is handled client-side (delete the token)
#For refresh token invalidation, implement a token blacklist in Redis
    return None

