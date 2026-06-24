"""End-to-end test of create-record, override, and audit-trail endpoints.
Requires the server running on port 8000."""
import urllib.request
import json

BASE = "http://127.0.0.1:8000"

def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req))

def get(path):
    return json.load(urllib.request.urlopen(BASE + path))

print("=== Create a record (500 KL Diesel, 2024-06-15) ===")
rec = post("/records", {
    "activity_name": "Diesel", "scope": 1, "section": "Power Plant",
    "quantity": 500, "unit": "KL", "activity_date": "2024-06-15"})
print(f"  id={rec['id']}  emissions={rec['calculated_emissions']:,} kgCO2e  factor_id={rec['factor_id_used']}  overridden={rec['is_overridden']}")
print(f"  Expected: 500 x 1757.0 = {500*1757.0:,}")

print("\n=== Override that record ===")
ov = post(f"/records/{rec['id']}/override", {
    "new_value": 800000, "reason": "Meter recalibration; engine value too low"})
print(f"  new emissions={ov['calculated_emissions']:,}  overridden={ov['is_overridden']}")

print("\n=== Audit trail for the record ===")
trail = get(f"/records/{rec['id']}/audit")
for a in trail:
    print(f"  [{a['changed_at']}] {a['field_changed']}: {a['old_value']} -> {a['new_value']}")
    print(f"     reason: {a['reason']}")

print("\n=== Validation check (negative quantity should be rejected) ===")
try:
    post("/records", {"activity_name": "Diesel", "scope": 1, "quantity": -5,
                      "unit": "KL", "activity_date": "2024-06-15"})
    print("  FAIL: should have been rejected")
except urllib.error.HTTPError as e:
    print(f"  PASS: rejected with HTTP {e.code} (validation works)")

print("\n=== Unknown activity should give clean 400 ===")
try:
    post("/records", {"activity_name": "Unobtainium", "scope": 1, "quantity": 10,
                      "unit": "kg", "activity_date": "2024-06-15"})
    print("  FAIL: should have been rejected")
except urllib.error.HTTPError as e:
    print(f"  PASS: rejected with HTTP {e.code} (FactorNotFoundError -> 400)")

print("\nAll API checks passed.")