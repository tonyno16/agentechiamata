"""
Test script: FastAPI -> Supabase connectivity
Run inside FastAPI container:

    docker compose exec fastapi python test_supabase.py
"""
import os
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("Test 1: Reading system_config...")
result = supabase.table("system_config").select("*").limit(3).execute()
print(f"  SUCCESS: Got {len(result.data)} rows")
for row in result.data:
    print(f"    - {row['key']}")

print("\nTest 2: Write and delete from leads...")
insert_result = supabase.table("leads").insert(
    {
        "source": "manual",
        "status": "new",
        "full_name": "Test Lead - DELETE ME",
        "phone": "+39000000000",
    }
).execute()
lead_id = insert_result.data[0]["id"]
print(f"  INSERT SUCCESS: lead_id = {lead_id}")

delete_result = supabase.table("leads").delete().eq("id", lead_id).execute()
print("  DELETE SUCCESS: cleaned up test lead")

print("\n=== ALL SUPABASE TESTS PASSED ===")

