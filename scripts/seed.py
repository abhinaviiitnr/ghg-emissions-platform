"""
Seed the GHG database from GHG_Sheet_.xlsx.

Builds a versioned, two-year dataset from a single-year source spreadsheet.
The provided sheet has no year dimension and no factor versioning, so this
script CONSTRUCTS a defensible historical dataset:

  * Factors converted tCO2/unit -> kgCO2e/unit (x1000) to match the brief.
  * 2024 = "current year", seeded directly from the sheet (factor version 2).
  * 2023 = "prior year", synthesized: factors scaled x0.95 (version 1) and
    quantities scaled down per-activity by a fixed-seed random factor in
    [0.88, 0.95], so YoY shows a realistic mixed decline.
  * Records store NO factor; the engine looks it up by activity + date,
    computes quantity x factor, stores the result + the factor id used.
  * BusinessMetrics (steel production) are constructed; the sheet has none.

The source sheet classifies many non-combustion materials (process gases,
intermediates, industrial gases) as Scope 1, which inflates absolute totals
beyond a real steel plant's intensity. The platform ingests the data
faithfully rather than curating it -- see README "Data provenance".

All synthetic choices are deterministic (random.seed(42)).
"""
import sys
import random
from pathlib import Path
from datetime import date

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from api.database import engine, SessionLocal, Base
from api import models

random.seed(42)

RAW_XLSX = Path(__file__).resolve().parent.parent / "data" / "raw" / "GHG_Sheet_.xlsx"
TCO2_TO_KGCO2E = 1000.0
FACTOR_DRIFT_2023 = 0.95
SOURCE_S2_DEFAULT = "CEA India 2023 Report"

QUARTER_MONTH = {"Q1": 2, "Q2": 5, "Q3": 8, "Q4": 11}


def load_and_normalize():
    """Read both sheets, return a unified DataFrame of activities."""
    xl = pd.ExcelFile(RAW_XLSX)

    s1 = pd.read_excel(xl, sheet_name="Scope 1")
    s1n = pd.DataFrame({
        "activity_name": s1["Material"].astype(str).str.strip(),
        "section": s1["Section"].astype(str).str.strip(),
        "quantity": pd.to_numeric(s1["Q1 Quantity"], errors="coerce"),
        "unit": s1["Unit of Material"].astype(str).str.strip(),
        "factor_tco2": pd.to_numeric(s1["Emission Factor"], errors="coerce"),
        "source": s1["Data Source for Emission Factor"].astype(str).str.strip(),
        "quarter": s1["Year/Timeline"].astype(str).str.strip(),
        "scope": 1,
    })

    s2 = pd.read_excel(xl, sheet_name="Scope 2")
    s2n = pd.DataFrame({
        "activity_name": s2["Supplier/Source"].astype(str).str.strip(),
        "section": s2["Section/Process"].astype(str).str.strip(),
        "quantity": pd.to_numeric(s2["Energy Consumed"], errors="coerce"),
        "unit": s2["Unit"].astype(str).str.strip(),
        "factor_tco2": pd.to_numeric(s2["Emission Factor (tCO₂/unit)"], errors="coerce"),
        "source": SOURCE_S2_DEFAULT,
        "quarter": s2["Quarter"].astype(str).str.strip(),
        "scope": 2,
    })

    df = pd.concat([s1n, s2n], ignore_index=True)
    df = df.dropna(subset=["quantity", "factor_tco2"])
    df = df[df["quantity"] > 0]
    return df


def build_factors(df):
    """One canonical factor per activity (first occurrence)."""
    factors = {}
    for _, row in df.iterrows():
        name = row["activity_name"]
        if name in factors:
            continue
        factors[name] = {
            "scope": int(row["scope"]),
            "unit": row["unit"],
            "factor_kg_2024": row["factor_tco2"] * TCO2_TO_KGCO2E,
            "source": row["source"],
        }
    return factors


def main():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    df = load_and_normalize()
    factors = build_factors(df)
    print(f"Loaded {len(df)} activity rows, {len(factors)} unique activities.")

    factor_lookup = {}
    for name, f in factors.items():
        f2023 = models.EmissionFactor(
            activity_name=name, scope=f["scope"], unit=f["unit"],
            co2e_factor=round(f["factor_kg_2024"] * FACTOR_DRIFT_2023, 4),
            source=f["source"],
            valid_from=date(2023, 1, 1), valid_to=date(2023, 12, 31), version=1,
        )
        f2024 = models.EmissionFactor(
            activity_name=name, scope=f["scope"], unit=f["unit"],
            co2e_factor=round(f["factor_kg_2024"], 4),
            source=f["source"],
            valid_from=date(2024, 1, 1), valid_to=None, version=2,
        )
        db.add(f2023); db.add(f2024)
        db.flush()
        factor_lookup[(name, 2023)] = f2023
        factor_lookup[(name, 2024)] = f2024

    qty_scale_2023 = {name: random.uniform(0.88, 0.95) for name in factors}

    n_2024 = n_2023 = 0
    for _, row in df.iterrows():
        name = row["activity_name"]
        q = row["quarter"] if row["quarter"] in QUARTER_MONTH else "Q1"
        month = QUARTER_MONTH[q]

        f24 = factor_lookup[(name, 2024)]
        d24 = date(2024, month, 15)
        emis24 = row["quantity"] * f24.co2e_factor
        db.add(models.EmissionRecord(
            activity_name=name, scope=int(row["scope"]), section=row["section"],
            quantity=float(row["quantity"]), unit=row["unit"], activity_date=d24,
            calculated_emissions=round(emis24, 4), factor_id_used=f24.id,
        ))
        n_2024 += 1

        f23 = factor_lookup[(name, 2023)]
        d23 = date(2023, month, 15)
        q23 = row["quantity"] * qty_scale_2023[name]
        emis23 = q23 * f23.co2e_factor
        db.add(models.EmissionRecord(
            activity_name=name, scope=int(row["scope"]), section=row["section"],
            quantity=round(float(q23), 4), unit=row["unit"], activity_date=d23,
            calculated_emissions=round(emis23, 4), factor_id_used=f23.id,
        ))
        n_2023 += 1

    metric_name = "Tonnes of Steel Produced"
    base_2024 = 2_000_000
    for year, factor in [(2023, 0.92), (2024, 1.0)]:
        for m in range(1, 13):
            monthly = base_2024 * factor * random.uniform(0.95, 1.05)
            db.add(models.BusinessMetric(
                metric_date=date(year, m, 28),
                metric_name=metric_name, value=round(monthly, 2),
            ))

    db.commit()

    nf = db.query(models.EmissionFactor).count()
    nr = db.query(models.EmissionRecord).count()
    nm = db.query(models.BusinessMetric).count()
    print(f"Inserted: {nf} factors, {nr} records ({n_2024} in 2024, {n_2023} in 2023), {nm} business metrics.")
    db.close()


if __name__ == "__main__":
    main()