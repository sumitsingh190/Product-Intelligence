from fastapi import APIRouter
from app.api.v1.endpoints import auth, data_sources, insights, workspaces,search
api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
api_router.include_router(workspaces.router, prefix='/workspaces', tags=['Workspaces'])
api_router.include_router(data_sources.router, prefix='/data-sources', tags=['Data Sources'])
api_router.include_router(insights.router, prefix='/insights', tags=['Insights'])
