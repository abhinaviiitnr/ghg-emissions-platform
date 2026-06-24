from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


class EmissionFactor(Base):
    """Versioned emission factors. For any (activity, date) exactly one row
    should be valid. This is what powers historical-accuracy lookups."""
    __tablename__ = "emission_factors"

    id = Column(Integer, primary_key=True, index=True)
    activity_name = Column(String, nullable=False, index=True)
    scope = Column(Integer, nullable=False)          # 1 or 2
    unit = Column(String, nullable=False)            # unit of the activity
    co2e_factor = Column(Float, nullable=False)      # kgCO2e per unit
    source = Column(String, nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)           # null = currently active
    version = Column(Integer, nullable=False, default=1)

    records = relationship("EmissionRecord", back_populates="factor")


class EmissionRecord(Base):
    """One recorded activity. Note: NO factor stored here -- it is looked up
    by activity_name + activity_date at calculation time, then the resulting
    emissions and the factor version actually used are stored for traceability."""
    __tablename__ = "emission_records"

    id = Column(Integer, primary_key=True, index=True)
    activity_name = Column(String, nullable=False, index=True)
    scope = Column(Integer, nullable=False)
    section = Column(String, nullable=True)          # e.g. "Pellet Plant", "EAF"
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    activity_date = Column(Date, nullable=False, index=True)
    calculated_emissions = Column(Float, nullable=False)   # kgCO2e
    factor_id_used = Column(Integer, ForeignKey("emission_factors.id"))
    is_overridden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    factor = relationship("EmissionFactor", back_populates="records")
    audit_entries = relationship("AuditLog", back_populates="record")


class BusinessMetric(Base):
    """Production / business figures used for emission intensity
    (e.g. kgCO2e per tonne of steel). The provided sheet has none of these,
    so these are constructed and documented in the seed script."""
    __tablename__ = "business_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)


class AuditLog(Base):
    """Records every manual override applied to an EmissionRecord."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("emission_records.id"), nullable=False)
    field_changed = Column(String, nullable=False)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    record = relationship("EmissionRecord", back_populates="audit_entries")