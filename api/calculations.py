"""
Core emission calculation engine.

The central requirement of the assignment: emissions must be calculated using
the emission factor that was VALID AT THE TIME of the activity -- not simply
the latest factor. These functions implement that date-aware lookup and the
fundamental Activity x Factor calculation.
"""
from datetime import date
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models


class FactorNotFoundError(Exception):
    """Raised when no emission factor is valid for the given activity + date."""
    pass


def get_valid_factor(db: Session, activity_name: str, on_date: date) -> models.EmissionFactor:
    """Return the single emission factor valid for `activity_name` on `on_date`.

    A factor is valid when:  valid_from <= on_date <= valid_to
    (valid_to = NULL means the factor is still active, i.e. open-ended.)

    This is what enforces 'historical accuracy': a 2023 activity resolves to the
    2023 factor version, a 2024 activity to the 2024 version.
    """
    factor = (
        db.query(models.EmissionFactor)
        .filter(
            models.EmissionFactor.activity_name == activity_name,
            models.EmissionFactor.valid_from <= on_date,
            or_(
                models.EmissionFactor.valid_to == None,   # noqa: E711  (SQL IS NULL)
                models.EmissionFactor.valid_to >= on_date,
            ),
        )
        .order_by(models.EmissionFactor.valid_from.desc())  # newest valid wins
        .first()
    )
    if factor is None:
        raise FactorNotFoundError(
            f"No emission factor valid for '{activity_name}' on {on_date}."
        )
    return factor


def calculate_emissions(db: Session, activity_name: str, quantity: float, on_date: date):
    """Compute emissions = quantity x (date-correct factor).

    Returns (emissions_kgco2e, factor_used). Returning the factor object too
    lets callers record exactly which version was applied -- important for
    traceability and the override/audit trail.
    """
    factor = get_valid_factor(db, activity_name, on_date)
    emissions = quantity * factor.co2e_factor
    return emissions, factor