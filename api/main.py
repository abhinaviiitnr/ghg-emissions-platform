"""
FastAPI application: serves the analytics endpoints and (later) the dashboard.

Endpoints in this version:
  GET /health                          -- liveness check
  GET /info                            -- model/data metadata
  GET /analytics/yoy?year=2024         -- YoY emissions by scope (stacked bar)
  GET /analytics/intensity?year=2024   -- emission intensity (KPI card)
  GET /analytics/hotspot?year=2024     -- emissions by source (donut)
  GET /analytics/trend?year=2024       -- monthly emission totals (line chart)
"""
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from . import schemas
from .calculations import calculate_emissions, FactorNotFoundError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.responses import FileResponse
from pathlib import Path

from . import analytics, models
from .database import get_db

app = FastAPI(title="GHG Emissions Reporting Platform", version="1.0")

# Allow the frontend (served from the same app, but also any local origin during
# development) to call these endpoints from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info(db: Session = Depends(get_db)):
    """Metadata about the loaded dataset: counts and the year range available."""
    n_factors = db.query(models.EmissionFactor).count()
    n_records = db.query(models.EmissionRecord).count()
    n_metrics = db.query(models.BusinessMetric).count()
    years = db.query(
        func.min(models.EmissionRecord.activity_date),
        func.max(models.EmissionRecord.activity_date),
    ).first()
    return {
        "factors": n_factors,
        "records": n_records,
        "business_metrics": n_metrics,
        "date_range": {
            "from": str(years[0]) if years[0] else None,
            "to": str(years[1]) if years[1] else None,
        },
    }


@app.get("/analytics/yoy")
def get_yoy(year: int = Query(2024), db: Session = Depends(get_db)):
    return analytics.yoy_by_scope(db, year)


@app.get("/analytics/intensity")
def get_intensity(year: int = Query(2024), db: Session = Depends(get_db)):
    return analytics.emission_intensity(db, year)


@app.get("/analytics/hotspot")
def get_hotspot(year: int = Query(2024), top_n: int = Query(8), db: Session = Depends(get_db)):
    return analytics.emission_hotspot(db, year, top_n)


@app.get("/analytics/trend")
def get_trend(year: int = Query(2024), db: Session = Depends(get_db)):
    return analytics.monthly_trend(db, year)
@app.post("/records", response_model=schemas.EmissionRecordOut)
def create_record(payload: schemas.EmissionRecordCreate, db: Session = Depends(get_db)):
    """Create a Scope 1 or 2 emission record. Emissions are computed by the
    engine using the factor valid on activity_date -- caller supplies no factor."""
    try:
        emissions, factor = calculate_emissions(
            db, payload.activity_name, payload.quantity, payload.activity_date
        )
    except FactorNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = models.EmissionRecord(
        activity_name=payload.activity_name,
        scope=payload.scope,
        section=payload.section,
        quantity=payload.quantity,
        unit=payload.unit,
        activity_date=payload.activity_date,
        calculated_emissions=round(emissions, 4),
        factor_id_used=factor.id,
        is_overridden=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.post("/records/{record_id}/override", response_model=schemas.EmissionRecordOut)
def override_record(record_id: int, payload: schemas.OverrideRequest, db: Session = Depends(get_db)):
    """Manually override a record's emissions, writing a full audit entry."""
    record = db.query(models.EmissionRecord).filter_by(id=record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found.")

    old_value = record.calculated_emissions

    audit = models.AuditLog(
        record_id=record.id,
        field_changed="calculated_emissions",
        old_value=str(old_value),
        new_value=str(payload.new_value),
        reason=payload.reason,
    )
    db.add(audit)

    record.calculated_emissions = payload.new_value
    record.is_overridden = True

    db.commit()
    db.refresh(record)
    return record


@app.get("/records/{record_id}/audit", response_model=list[schemas.AuditLogOut])
def get_audit_trail(record_id: int, db: Session = Depends(get_db)):
    """Return the full audit history for a record."""
    return (
        db.query(models.AuditLog)
        .filter_by(record_id=record_id)
        .order_by(models.AuditLog.changed_at)
        .all()
    )
@app.post("/metrics", response_model=schemas.BusinessMetricOut)
def create_metric(payload: schemas.BusinessMetricCreate, db: Session = Depends(get_db)):
    """Create a business metric (e.g. tonnes of steel produced) used as the
    denominator for emission intensity."""
    metric = models.BusinessMetric(
        metric_name=payload.metric_name,
        value=payload.value,
        metric_date=payload.metric_date,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric

@app.get("/activities")
def list_activities(db: Session = Depends(get_db)):
    """Distinct known activities with unit/section/scope, for the frontend
    dropdowns. Derived from the currently-active factor versions."""
    factors = (
        db.query(models.EmissionFactor)
        .filter(models.EmissionFactor.valid_to == None)  # noqa: E711
        .order_by(models.EmissionFactor.activity_name)
        .all()
    )
    out = []
    for f in factors:
        rec = (
            db.query(models.EmissionRecord.section)
            .filter(models.EmissionRecord.activity_name == f.activity_name,
                    models.EmissionRecord.section.isnot(None))
            .first()
        )
        out.append({
            "activity_name": f.activity_name, "scope": f.scope,
            "unit": f.unit, "section": rec[0] if rec else None,
        })
    return out


@app.get("/records")
def list_records(limit: int = Query(15), db: Session = Depends(get_db)):
    """Most recent emission records, newest first, for the records table."""
    rows = (
        db.query(models.EmissionRecord)
        .order_by(models.EmissionRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [{
        "id": r.id, "activity_name": r.activity_name, "scope": r.scope,
        "section": r.section, "quantity": r.quantity, "unit": r.unit,
        "activity_date": str(r.activity_date),
        "calculated_emissions": r.calculated_emissions,
        "is_overridden": r.is_overridden,
    } for r in rows]


# --- Serve the frontend (must be defined AFTER all API routes) ---
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
def dashboard():
    """Serve the single-page dashboard."""
    return FileResponse(FRONTEND_DIR / "index.html")