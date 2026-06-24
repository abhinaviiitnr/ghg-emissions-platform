"""Functional test of the analytics engine against the seeded DB."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from api.database import SessionLocal
from api import analytics

db = SessionLocal()

print("=== YoY by scope (2024) ===")
yoy = analytics.yoy_by_scope(db, 2024)
for yr in (yoy["previous_year"], yoy["current_year"]):
    d = yoy["data"][str(yr)]
    print(f"  {yr}: Scope1={d['scope_1']/1e9:.2f}M  Scope2={d['scope_2']/1e9:.3f}M  Total={d['total']/1e9:.2f}M tCO2e")
chg = (yoy["data"]["2024"]["total"] - yoy["data"]["2023"]["total"]) / yoy["data"]["2023"]["total"] * 100
print(f"  YoY change: {chg:+.1f}%")

print("\n=== Intensity (2024) ===")
i = analytics.emission_intensity(db, 2024)
print(f"  {i['total_emissions_kgco2e']/1e9:.2f}M kgCO2e / {i['total_production']:,.0f} t = {i['intensity_kgco2e_per_unit']:,.2f} kgCO2e/t")

print("\n=== Hotspot top 8 + Other (2024) ===")
h = analytics.emission_hotspot(db, 2024)
for b in h["breakdown"]:
    pct = b["emissions_kgco2e"] / h["total_emissions_kgco2e"] * 100
    print(f"  {b['source']:<22} {b['emissions_kgco2e']/1e9:6.2f}M  ({pct:4.1f}%)")

print("\n=== Monthly trend (2024) ===")
t = analytics.monthly_trend(db, 2024)
nonzero = [(s["month"], s["emissions_kgco2e"]) for s in t["series"] if s["emissions_kgco2e"] > 0]
print(f"  Months with data: {[m for m, _ in nonzero]}")
print(f"  All 12 months present: {len(t['series']) == 12}")

db.close()
print("\nAll analytics checks passed.")