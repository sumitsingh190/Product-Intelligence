from fastapi import APIRouter

from app.api.v1.endpoints import (
analytics,
auth,
data_sources,
insights,
recommendations,
reports,
search,
workspaces,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["Data Sources"])
api_router.include_router(insights.router, prefix="/insights", tags=["Insights"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"]) 
api_router.include_router(search.router, prefix="/search", tags=["Search"])