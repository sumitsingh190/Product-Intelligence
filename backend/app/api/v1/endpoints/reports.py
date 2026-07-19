from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.deps import CurrentUserDep, SessionDep, ensure_workspace_access
from app.schemas.common import PaginatedResponse

router=APIRouter()

ReportType= Literal["prd", "sprint_plan", "executive_report", "product_health"]

@router.get("")
async def list_reports(
    workspace_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query (20, ge=1, le=100),
):
    ensure_workspace_access(current_user, workspace_id) 
    from app.models.document import Document
    from sqlalchemy import func, select

    result = await db.execute(
        select(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    documents = result.scalars().all()
    count_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.workspace_id == workspace_id) )
    total = count_result.scalar_one()
    pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=documents, total=total, page=page, page_size=page_size, pages=pages)

@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    workspace_id: str,
    report_type: ReportType,
    current_user: CurrentUserDep,
    db: SessionDep,
    recommendation_id: str | None=Query(
        None, description="Optional: generate PRD for a specific recommendation"
    ),):

    ensure_workspace_access(current_user, workspace_id)
    from app.tasks.reporting_tasks import generate_report_task
    task = generate_report_task.delay(workspace_id, report_type, recommendation_id)
    return {"task_id": task.id, "status": "queued", "report_type": report_type}

@router.get("/{document_id}")
async def get_report(document_id: str, current_user: CurrentUserDep, db: SessionDep): 
    from app.models.document import Document
    from sqlalchemy import select

    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found") 
    ensure_workspace_access(current_user, document.workspace_id)
    return document

@router.get("/{document_id}/export")
async def export_report(
    document_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
    format: Literal["markdown", "pdf", "html"] = "markdown",
):
    from app.models.document import Document 
    from sqlalchemy import select
    
    result=await db.execute(select(Document).where(Document.id == document_id))
    document=result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found") 
    ensure_workspace_access(current_user, document.workspace_id)
    
    safe_filename = "".join(c if c.isalnum() or c in "=_." else "_" for c in document.title)

    if format == "markdown":
        return Response(
            content=document.content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}.md"'},
        )
    
    import markdown as md 
    html_body = md.markdown(
        document.content, extensions=["extra", "tables", "fenced_code", "sane_lists"],
    )
    html_full= _wrap_html(document.title, html_body)

    if format == "html":
        return Response(content=html_full, media_type="text/html")
    
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_full).write_pdf()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF rendering failed: {e}",
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}.pdf"'},
    )

def _wrap_html(title: str, body_html: str) -> str:

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset=\"utf-8\" />
<title>{title}</title>
<style>
    @page {{ size: A4; margins: 2cm; }}
    body {{ font-family: -apple-system, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; color: #1f2937; line-height: 1.5; font-size: 11pt; }}
    h1 {{ font-size: 22pt; margin-bottom: 0.5em; border-bottom: 2px solid #6366f1; padding-bottom: 0.2em; }}
    h2 {{ font-size: 15pt; margin-top: 1.5em; color: #4f46e5; }}
    h3 {{ font-size: 12pt; margin-top: 1em; }}
    code {{ background: #f3f4f6; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.95em; }}
    pre {{ background: #f3f4f6; padding: 0.8em; border-radius: 5px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 0.4em 0.6em; text-align: left; }}
    th {{ background: #f9fafb; }}
    blockquote {{ border-left: 3px solid #c7d2fe; padding-left: 1em; color: #4b5563; }}
    ul, ol {{ padding-left: 1.6em; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""