import sys
import pandas as pd
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent))

from generate_test_data import generate_test_data
from services.excel_db import ExcelDB
from services.ola_maps import OlaMapsClient
from services.matching import MatchingService

def run_integration_test():
    print("=== STARTING SYSTEM INTEGRATION TEST ===")
    
    # 1. Generate test data
    generate_test_data()
    
    # 2. Ingest Excel files into the unified Excel Database
    print("\n[Step 2] Ingesting files into database.xlsx...")
    vol_df = pd.read_excel("data/volunteers.xlsx")
    stud_df = pd.read_excel("data/students.xlsx")
    
    vol_records = []
    for idx, row in vol_df.iterrows():
        vol_records.append({
            "id": str(row["ID"]),
            "name": str(row["Name"]),
            "address": str(row["Address"]),
            "phone": str(row["Phone"]),
            "latitude": "",
            "longitude": "",
            "other_details": str({"Skill": row["Skill"]})
        })
        
    stud_records = []
    for idx, row in stud_df.iterrows():
        stud_records.append({
            "id": str(row["ID"]),
            "name": str(row["Name"]),
            "address": str(row["Address"]),
            "phone": str(row["Phone"]),
            "latitude": "",
            "longitude": "",
            "other_details": str({"Grade": row["Grade"]})
        })
        
    ExcelDB.write_sheet("volunteers", vol_records)
    ExcelDB.write_sheet("students", stud_records)
    print(f"Ingested {len(vol_records)} volunteers and {len(stud_records)} students.")
    
    # 3. Geocode
    print("\n[Step 3] Geocoding addresses...")
    volunteers = ExcelDB.read_sheet("volunteers")
    students = ExcelDB.read_sheet("students")
    ola_client = OlaMapsClient()
    
    geocoded_v = []
    for v in volunteers:
        coords = ola_client.geocode(v["address"])
        if coords:
            v["latitude"], v["longitude"] = coords
            ExcelDB.cache_coordinate(v["address"], coords[0], coords[1])
        geocoded_v.append(v)
        
    geocoded_s = []
    for s in students:
        coords = ola_client.geocode(s["address"])
        if coords:
            s["latitude"], s["longitude"] = coords
            ExcelDB.cache_coordinate(s["address"], coords[0], coords[1])
        geocoded_s.append(s)
        
    ExcelDB.write_sheet("volunteers", geocoded_v)
    ExcelDB.write_sheet("students", geocoded_s)
    print("Geocoding complete. Updated database.xlsx.")
    
    # 4. Calculate Distance Matrix
    print("\n[Step 4] Calculating routing distance matrix...")
    valid_volunteers = [(v["id"], float(v["latitude"]), float(v["longitude"])) for v in geocoded_v if v["latitude"]]
    valid_students = [(s["id"], float(s["latitude"]), float(s["longitude"])) for s in geocoded_s if s["latitude"]]
    
    distances = ola_client.get_distance_matrix(valid_volunteers, valid_students)
    ExcelDB.cache_distances(distances)
    print(f"Distance matrix calculation complete. Cached {len(distances)} pairs.")
    
    # 5. Matching Assignments
    print("\n[Step 5] Running Matching Engine...")
    dist_matrix = ExcelDB.get_distance_cache()
    assignments = MatchingService.generate_assignments(
        volunteers=geocoded_v,
        students=geocoded_s,
        distance_matrix=dist_matrix,
        max_students=4,
        prevent_duplicates=True
    )
    
    # Save assignments
    db_assignments = []
    for a in assignments:
        db_assignments.append({
            "volunteer_id": a["volunteer_id"],
            "volunteer_name": a["volunteer_name"],
            "student_id": a["student_id"],
            "student_name": a["student_name"],
            "distance_km": str(a["distance_km"]),
            "duration_minutes": str(a["duration_minutes"]),
            "assigned_at": "2026-06-04T14:20:00"
        })
    ExcelDB.write_sheet("assignments", db_assignments)
    print(f"Generated {len(assignments)} assignments successfully.")
    
    # Print results summary
    print("\n=== ASSIGNMENTS SUMMARY ===")
    vol_assignments_count = {}
    for a in assignments:
        v_name = a["volunteer_name"]
        vol_assignments_count[v_name] = vol_assignments_count.get(v_name, 0) + 1
        
    for vol, count in vol_assignments_count.items():
        print(f"Volunteer '{vol}': Assigned to {count} students.")
        
    print(f"Total students matched: {len(assignments)} / {len(students)}")
    print("=== INTEGRATION TEST COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_integration_test()
