# backend/app/routers/admin.py
"""Owner-only endpoints: load full Cricsheet match JSONs into the DB and
rebuild the prediction aggregation tables."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import require_admin, check_same_origin
from app.services.ingest import ingest_match, recent_matches, refresh_aggregations

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_DEPS = [Depends(check_same_origin), Depends(require_admin)]


class IngestRequest(BaseModel):
    match_json: dict = Field(..., description="Full Cricsheet v1.2.0 match JSON", alias="json")
    match_id: str | None = Field(None, max_length=50, description="Optional match id (defaults to a derived value)")

    model_config = {"populate_by_name": True}


@router.post("/ingest", dependencies=ADMIN_DEPS)
def admin_ingest(req: IngestRequest):
    """Insert a pasted/uploaded Cricsheet match JSON and refresh aggregations."""
    try:
        return ingest_match(req.match_json, req.match_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")


@router.post("/refresh", dependencies=ADMIN_DEPS)
def admin_refresh():
    """Re-run the aggregation rebuild without adding any match."""
    try:
        refresh_aggregations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e}")
    return {"ok": True}


@router.get("/matches", dependencies=ADMIN_DEPS)
def admin_matches(limit: int = 10):
    """Most recently loaded CPL matches (dedup check for the admin page)."""
    return {"matches": recent_matches(limit)}
