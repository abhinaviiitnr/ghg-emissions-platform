"""
Advanced analytics engine -- the core scored capability of the platform.

Four pure query functions, each independently testable, that power the
mandatory dashboard visualizations:
  * yoy_by_scope        -> stacked bar (Scope 1 vs 2, current vs previous year)
  * emission_intensity  -> KPI card (kgCO2e per tonne of product)
  * emission_hotspot    -> donut (top contributing sources)
  * monthly_trend       -> line chart (monthly totals across a year)

These read the calculated_emissions already stored on each record. Because the
seed/engine computed those with the DATE-CORRECT factor, year-over-year
differences faithfully reflect both quantity and factor changes.
"""
from datetime import date
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from . import models


def _year_bounds(year: int):
    return date(year, 1, 1), date(year, 12, 31)


def yoy_by_scope(db: Session, current_year: int):
    """Total emissions by scope for current_year and the year before it.

    Returns:
      {
        "current_year": 2024, "previous_year": 2023,
        "data": {
          "2024": {"scope_1": ..., "scope_2": ..., "total": ...},
          "2023": {"scope_1": ..., "scope_2": ..., "total": ...}
        }
      }
    """
    result = {}
    for year in (current_year - 1, current_year):
        start, end = _year_bounds(year)
        rows = (
            db.query(
                models.EmissionRecord.scope,
                func.sum(models.EmissionRecord.calculated_emissions),
            )
            .filter(models.EmissionRecord.activity_date >= start,
                    models.EmissionRecord.activity_date <= end)
            .group_by(models.EmissionRecord.scope)
            .all()
        )
        by_scope = {scope: total for scope, total in rows}
        s1 = by_scope.get(1, 0.0) or 0.0
        s2 = by_scope.get(2, 0.0) or 0.0
        result[str(year)] = {
            "scope_1": round(s1, 2),
            "scope_2": round(s2, 2),
            "total": round(s1 + s2, 2),
        }
    return {
        "current_year": current_year,
        "previous_year": current_year - 1,
        "data": result,
    }


def emission_intensity(db: Session, year: int, metric_name: str = "Tonnes of Steel Produced"):
    """kgCO2e per unit of production for a given year.

    intensity = total emissions / total production
    Returns None for intensity if there is no production data (avoids /0).
    """
    start, end = _year_bounds(year)

    total_emissions = (
        db.query(func.sum(models.EmissionRecord.calculated_emissions))
        .filter(models.EmissionRecord.activity_date >= start,
                models.EmissionRecord.activity_date <= end)
        .scalar()
    ) or 0.0

    total_production = (
        db.query(func.sum(models.BusinessMetric.value))
        .filter(models.BusinessMetric.metric_name == metric_name,
                models.BusinessMetric.metric_date >= start,
                models.BusinessMetric.metric_date <= end)
        .scalar()
    ) or 0.0

    intensity = (total_emissions / total_production) if total_production > 0 else None

    return {
        "year": year,
        "metric_name": metric_name,
        "total_emissions_kgco2e": round(total_emissions, 2),
        "total_production": round(total_production, 2),
        "intensity_kgco2e_per_unit": round(intensity, 4) if intensity is not None else None,
    }


def emission_hotspot(db: Session, year: int, top_n: int = 8):
    """Emissions broken down by source (activity) for a year, biggest first.

    Returns the top_n contributors individually plus an aggregated 'Other'
    bucket, so a donut chart stays readable. total_emissions lets the frontend
    compute percentages.
    """
    start, end = _year_bounds(year)
    rows = (
        db.query(
            models.EmissionRecord.activity_name,
            func.sum(models.EmissionRecord.calculated_emissions).label("emissions"),
        )
        .filter(models.EmissionRecord.activity_date >= start,
                models.EmissionRecord.activity_date <= end)
        .group_by(models.EmissionRecord.activity_name)
        .order_by(func.sum(models.EmissionRecord.calculated_emissions).desc())
        .all()
    )

    total = sum(e for _, e in rows) or 0.0
    top = rows[:top_n]
    other_sum = sum(e for _, e in rows[top_n:])

    breakdown = [{"source": name, "emissions_kgco2e": round(e, 2)} for name, e in top]
    if other_sum > 0:
        breakdown.append({"source": "Other", "emissions_kgco2e": round(other_sum, 2)})

    return {
        "year": year,
        "total_emissions_kgco2e": round(total, 2),
        "breakdown": breakdown,
    }


def monthly_trend(db: Session, year: int):
    """Total emissions per month for a year -> line chart.

    Returns all 12 months, zero-filled where there's no data, so the line
    chart has a continuous x-axis.
    """
    start, end = _year_bounds(year)
    rows = (
        db.query(
            extract("month", models.EmissionRecord.activity_date).label("month"),
            func.sum(models.EmissionRecord.calculated_emissions),
        )
        .filter(models.EmissionRecord.activity_date >= start,
                models.EmissionRecord.activity_date <= end)
        .group_by(extract("month", models.EmissionRecord.activity_date))
        .all()
    )
    by_month = {int(m): float(t) for m, t in rows}
    series = [{"month": m, "emissions_kgco2e": round(by_month.get(m, 0.0), 2)} for m in range(1, 13)]
    return {"year": year, "series": series}