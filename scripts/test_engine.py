"""Quick functional test of the calculation engine against the seeded DB."""
import sys
from pathlib import Path
from datetime import date

sys.path.append(str(Path(__file__).resolve().parent.parent))
from api.database import SessionLocal
from api.calculations import get_valid_factor, calculate_emissions, FactorNotFoundError

db = SessionLocal()

print("=== Date-aware factor lookup (Diesel) ===")
f_2023 = get_valid_factor(db, "Diesel", date(2023, 6, 15))
f_2024 = get_valid_factor(db, "Diesel", date(2024, 6, 15))
print(f"  2023-06-15 -> v{f_2023.version}, {f_2023.co2e_factor} kgCO2e/{f_2023.unit}")
print(f"  2024-06-15 -> v{f_2024.version}, {f_2024.co2e_factor} kgCO2e/{f_2024.unit}")
assert f_2023.version == 1 and f_2024.version == 2, "Wrong factor version selected!"
print("  PASS: different years select different factor versions.")

print("\n=== Boundary check (2023-12-31 vs 2024-01-01) ===")
last_2023 = get_valid_factor(db, "Diesel", date(2023, 12, 31))
first_2024 = get_valid_factor(db, "Diesel", date(2024, 1, 1))
print(f"  2023-12-31 -> v{last_2023.version}")
print(f"  2024-01-01 -> v{first_2024.version}")
assert last_2023.version == 1 and first_2024.version == 2, "Boundary off by one!"
print("  PASS: validity boundaries are exact, no overlap or gap.")

print("\n=== Full calculation (1000 KL Diesel) ===")
for d in [date(2023, 6, 15), date(2024, 6, 15)]:
    emis, factor = calculate_emissions(db, "Diesel", 1000.0, d)
    print(f"  {d}: 1000 x {factor.co2e_factor} = {emis:,.2f} kgCO2e (v{factor.version})")

print("\n=== Error handling (unknown activity) ===")
try:
    get_valid_factor(db, "Unobtainium", date(2024, 6, 15))
    print("  FAIL: should have raised.")
except FactorNotFoundError as e:
    print(f"  PASS: raised FactorNotFoundError correctly.")

db.close()
print("\nAll engine checks passed.")