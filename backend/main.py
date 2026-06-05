import io
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import DEFAULT_MAX_STUDENTS_PER_VOLUNTEER, DEFAULT_PREVENT_DUPLICATES, DATABASE_EXCEL_PATH
from services.excel_db import ExcelDB
from services.ola_maps import OlaMapsClient
from services.matching import MatchingService

app = FastAPI(
    title="Volunteer-Student Mapping API",
    description="Backend API for mapping volunteers to their nearest students using Ola Maps API and Excel storage.",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Ola Maps Client
ola_client = OlaMapsClient()

class AssignmentConfig(BaseModel):
    max_students_per_volunteer: int = DEFAULT_MAX_STUDENTS_PER_VOLUNTEER
    prevent_duplicate_assignments: bool = DEFAULT_PREVENT_DUPLICATES

def validate_excel_data(df: pd.DataFrame, file_type: str) -> Dict[str, Any]:
    """
    Validates Excel dataframe:
    - Identifies empty rows
    - Identifies missing addresses
    - Identifies duplicate records (by ID or Phone)
    """
    errors = []
    duplicates = []
    valid_records = []
    
    # Standardize column names (strip whitespace, lowercase)
    df.columns = [str(col).strip().lower() for col in df.columns]
    
    # Map required columns
    col_mapping = {}
    for col in df.columns:
        if "id" in col:
            col_mapping["id"] = col
        elif "name" in col:
            col_mapping["name"] = col
        elif "address" in col:
            col_mapping["address"] = col
        elif "phone" in col:
            col_mapping["phone"] = col
            
    # Check for critical columns
    required_cols = ["id", "name", "address"]
    missing_cols = [c for c in required_cols if c not in col_mapping]
    if missing_cols:
        raise HTTPException(
            status_code=400, 
            detail=f"Uploaded sheet is missing required columns. Could not identify: {', '.join(missing_cols)}"
        )
        
    seen_ids = set()
    seen_phones = set()
    
    for idx, row in df.iterrows():
        row_num = idx + 2 # 1-based, plus header row
        
        # Check for empty row
        if row.isna().all() or all(str(val).strip() == "" for val in row.values):
            errors.append(f"Row {row_num}: Empty row detected (Skipped)")
            continue
            
        r_id = str(row[col_mapping["id"]]).strip()
        r_name = str(row[col_mapping["name"]]).strip()
        r_address = str(row[col_mapping["address"]]).strip()
        r_phone = str(row[col_mapping["phone"]]).strip() if "phone" in col_mapping else ""
        
        # Extract other details
        other_details = {}
        for col in df.columns:
            if col not in col_mapping.values():
                val = row[col]
                if pd.notna(val):
                    other_details[col] = str(val).strip()
        
        # Check validation rules
        if not r_id or r_id == "nan":
            errors.append(f"Row {row_num}: Missing ID")
            continue
            
        if not r_name or r_name == "nan":
            errors.append(f"Row {row_num}: Missing Name")
            continue
            
        if not r_address or r_address == "nan" or r_address.lower() == "none":
            errors.append(f"Row {row_num} ({r_name}): Missing Address")
            continue
            
        # Check duplicates
        if r_id in seen_ids:
            duplicates.append(f"Row {row_num} ({r_name}): Duplicate ID '{r_id}'")
            continue
        if r_phone and r_phone in seen_phones and r_phone != "nan":
            duplicates.append(f"Row {row_num} ({r_name}): Duplicate Phone number '{r_phone}'")
            continue
            
        seen_ids.add(r_id)
        if r_phone and r_phone != "nan":
            seen_phones.add(r_phone)
            
        valid_records.append({
            "id": r_id,
            "name": r_name,
            "address": r_address,
            "phone": "" if r_phone == "nan" else r_phone,
            "latitude": "",
            "longitude": "",
            "other_details": str(other_details)
        })
        
    return {
        "records": valid_records,
        "errors": errors,
        "duplicates": duplicates
    }

@app.post("/upload/{file_type}")
async def upload_file(file_type: str, file: UploadFile = File(...)):
    """
    Uploads volunteers or students Excel file, validates it, and saves it in the database.
    file_type must be 'volunteers' or 'students'
    """
    if file_type not in ["volunteers", "students"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Must be 'volunteers' or 'students'.")
        
    # Read Excel into memory
    contents = await file.read()
    try:
        # Read excel file
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read Excel file: {str(e)}")
        
    # Validate Excel data
    validation = validate_excel_data(df, file_type)
    
    # Save valid records to database sheet
    ExcelDB.write_sheet(file_type, validation["records"])
    
    # Log upload
    upload_record = {
        "upload_id": f"upl-{int(datetime.now().timestamp())}",
        "filename": file.filename,
        "file_type": file_type,
        "row_count": len(validation["records"]),
        "uploaded_at": datetime.now().isoformat()
    }
    ExcelDB.append_rows("uploads", [upload_record])
    
    return {
        "filename": file.filename,
        "processed_count": len(df),
        "valid_count": len(validation["records"]),
        "errors": validation["errors"],
        "duplicates": validation["duplicates"],
        "status": "success"
    }

@app.post("/geocode")
async def geocode_addresses():
    """
    Extracts addresses from both volunteers and students, converts them into latitude and longitude,
    caches them, and updates their records.
    """
    volunteers = ExcelDB.read_sheet("volunteers")
    students = ExcelDB.read_sheet("students")
    
    if not volunteers and not students:
        return {"status": "warning", "message": "No volunteer or student records found to geocode."}
        
    coord_cache = ExcelDB.get_coordinate_cache()
    
    geocoded_count = 0
    cached_count = 0
    failed_count = 0
    
    # Process Volunteers
    updated_volunteers = []
    for v in volunteers:
        addr = v.get("address", "").strip()
        addr_clean = addr.lower()
        
        # Check cache first
        if addr_clean in coord_cache:
            v["latitude"], v["longitude"] = coord_cache[addr_clean]
            cached_count += 1
        else:
            coords = ola_client.geocode(addr)
            if coords:
                v["latitude"], v["longitude"] = coords
                ExcelDB.cache_coordinate(addr, coords[0], coords[1])
                # Update local cache ref so we don't hit API again for identical address in same run
                coord_cache[addr_clean] = coords
                geocoded_count += 1
            else:
                v["latitude"], v["longitude"] = "", ""
                failed_count += 1
        updated_volunteers.append(v)
        
    # Process Students
    updated_students = []
    for s in students:
        addr = s.get("address", "").strip()
        addr_clean = addr.lower()
        
        # Check cache first
        if addr_clean in coord_cache:
            s["latitude"], s["longitude"] = coord_cache[addr_clean]
            cached_count += 1
        else:
            coords = ola_client.geocode(addr)
            if coords:
                s["latitude"], s["longitude"] = coords
                ExcelDB.cache_coordinate(addr, coords[0], coords[1])
                coord_cache[addr_clean] = coords
                geocoded_count += 1
            else:
                s["latitude"], s["longitude"] = "", ""
                failed_count += 1
        updated_students.append(s)
        
    # Save back
    ExcelDB.write_sheet("volunteers", updated_volunteers)
    ExcelDB.write_sheet("students", updated_students)
    
    return {
        "status": "success",
        "total_volunteers": len(volunteers),
        "total_students": len(students),
        "newly_geocoded": geocoded_count,
        "loaded_from_cache": cached_count,
        "failed_geocoding": failed_count
    }

@app.post("/calculate-distances")
async def calculate_distances():
    """
    Calculates road distances between all geocoded volunteers and students using Ola Maps Routing API.
    Caches distances to avoid redundant API queries.
    """
    volunteers = ExcelDB.read_sheet("volunteers")
    students = ExcelDB.read_sheet("students")
    
    # Filter only those with valid lat/lon
    valid_volunteers = []
    for v in volunteers:
        if v.get("latitude") and v.get("longitude"):
            try:
                valid_volunteers.append((v["id"], float(v["latitude"]), float(v["longitude"])))
            except ValueError:
                pass
                
    valid_students = []
    for s in students:
        if s.get("latitude") and s.get("longitude"):
            try:
                valid_students.append((s["id"], float(s["latitude"]), float(s["longitude"])))
            except ValueError:
                pass
                
    if not valid_volunteers or not valid_students:
        return {
            "status": "warning", 
            "message": f"Cannot calculate distances. Volunteers geocoded: {len(valid_volunteers)}/{len(volunteers)}, Students geocoded: {len(valid_students)}/{len(students)}"
        }
        
    # Load existing distance matrix from cache
    distance_cache = ExcelDB.get_distance_cache()
    
    # Find missing volunteer-student pairings
    missing_pairings = []
    origins_to_query = []
    destinations_to_query = []
    
    # Simple strategy: Query all pairs that are missing from cache
    # To optimize Ola Maps API calls, we collect all origins and destinations
    # and only request those pairs that are not cached yet.
    # Because DistanceMatrix calculates all combinations (origins x destinations),
    # we can construct smaller sub-matrices for missing combinations.
    # For simplicity and robust fallback, we filter out what's not in cache and query.
    for v_id, v_lat, v_lng in valid_volunteers:
        for s_id, s_lat, s_lng in valid_students:
            key = f"{v_id}:{s_id}"
            if key not in distance_cache:
                missing_pairings.append(((v_id, v_lat, v_lng), (s_id, s_lat, s_lng)))
                
    new_distances_count = 0
    cached_distances_count = len(valid_volunteers) * len(valid_students) - len(missing_pairings)
    
    if missing_pairings:
        # Group missing pairings to call Distance Matrix API
        # To avoid making N*M single HTTP requests, we query unique origins and their corresponding destinations.
        # Since Ola Maps can take a list of origins and destinations:
        # We can query all unique volunteers and destinations in batches.
        unique_origins = list({p[0] for p in missing_pairings})
        unique_destinations = list({p[1] for p in missing_pairings})
        
        # Call API
        api_results = ola_client.get_distance_matrix(unique_origins, unique_destinations)
        
        # Cache results
        if api_results:
            ExcelDB.cache_distances(api_results)
            new_distances_count = len(api_results)
            
    return {
        "status": "success",
        "total_pairs": len(valid_volunteers) * len(valid_students),
        "cached_pairs": cached_distances_count + new_distances_count,
        "newly_calculated_pairs": new_distances_count
    }

@app.post("/generate-assignments")
async def generate_assignments(config: AssignmentConfig):
    """
    Runs matching algorithm to assign volunteers to students and stores assignments in database.
    """
    volunteers = ExcelDB.read_sheet("volunteers")
    students = ExcelDB.read_sheet("students")
    
    if not volunteers or not students:
        raise HTTPException(status_code=400, detail="Cannot generate assignments. Volunteers or students data is empty.")
        
    distance_matrix = ExcelDB.get_distance_cache()
    
    # Generate assignments
    assignments = MatchingService.generate_assignments(
        volunteers=volunteers,
        students=students,
        distance_matrix=distance_matrix,
        max_students=config.max_students_per_volunteer,
        prevent_duplicates=config.prevent_duplicate_assignments
    )
    
    # Save assignments to sheet
    now_str = datetime.now().isoformat()
    db_assignments = []
    for a in assignments:
        db_assignments.append({
            "volunteer_id": a["volunteer_id"],
            "volunteer_name": a["volunteer_name"],
            "student_id": a["student_id"],
            "student_name": a["student_name"],
            "distance_km": str(a["distance_km"]),
            "duration_minutes": str(a["duration_minutes"]),
            "assigned_at": now_str
        })
        
    ExcelDB.write_sheet("assignments", db_assignments)
    
    return {
        "status": "success",
        "assignments_count": len(db_assignments),
        "assignments": db_assignments
    }

@app.get("/assignments")
async def get_assignments():
    """
    Returns current assignments.
    """
    assignments = ExcelDB.read_sheet("assignments")
    return {
        "status": "success",
        "count": len(assignments),
        "assignments": assignments
    }

@app.get("/stats")
async def get_stats():
    """
    Returns general stats for the dashboard.
    """
    volunteers = ExcelDB.read_sheet("volunteers")
    students = ExcelDB.read_sheet("students")
    coordinates = ExcelDB.read_sheet("coordinates")
    distance_matrix = ExcelDB.read_sheet("distance_matrix")
    assignments = ExcelDB.read_sheet("assignments")
    uploads = ExcelDB.read_sheet("uploads")
    
    # Calculate geocoded counts
    v_geocoded = sum(1 for v in volunteers if v.get("latitude") and v.get("longitude"))
    s_geocoded = sum(1 for s in students if s.get("latitude") and s.get("longitude"))
    
    # Find list of unassigned students
    assigned_student_ids = {a["student_id"] for a in assignments if a.get("student_id")}
    unassigned_students = [s for s in students if str(s["id"]) not in assigned_student_ids]
    
    # Average distance of assignments
    avg_dist = 0.0
    if assignments:
        try:
            avg_dist = sum(float(a["distance_km"]) for a in assignments if a.get("distance_km")) / len(assignments)
            avg_dist = round(avg_dist, 2)
        except Exception:
            pass
            
    return {
        "volunteers_count": len(volunteers),
        "volunteers_geocoded": v_geocoded,
        "students_count": len(students),
        "students_geocoded": s_geocoded,
        "coordinates_cache_count": len(coordinates),
        "distance_cache_count": len(distance_matrix),
        "assignments_count": len(assignments),
        "unassigned_students_count": len(unassigned_students),
        "average_distance_km": avg_dist,
        "uploads": uploads[-10:] if uploads else [] # Return last 10 uploads
    }

@app.get("/download-report")
async def download_report():
    """
    Generates and returns an Excel report containing:
    1. Summary metrics sheet
    2. Detailed volunteer-student mappings sheet
    3. List of unassigned students sheet
    4. List of unassigned volunteers sheet
    """
    volunteers = ExcelDB.read_sheet("volunteers")
    students = ExcelDB.read_sheet("students")
    assignments = ExcelDB.read_sheet("assignments")
    
    # Create DataFrames
    df_volunteers = pd.DataFrame(volunteers)
    df_students = pd.DataFrame(students)
    df_assignments = pd.DataFrame(assignments)
    
    # 1. Summary sheet metrics
    total_vol = len(volunteers)
    total_stud = len(students)
    total_assigned = len(df_assignments["student_id"].unique()) if not df_assignments.empty else 0
    unassigned_stud = total_stud - total_assigned
    
    avg_dist = 0.0
    max_dist = 0.0
    if not df_assignments.empty:
        try:
            distances = df_assignments["distance_km"].astype(float)
            avg_dist = round(distances.mean(), 2)
            max_dist = round(distances.max(), 2)
        except Exception:
            pass
            
    summary_data = {
        "Metric": [
            "Total Volunteers Uploaded",
            "Total Students Uploaded",
            "Assigned Students",
            "Unassigned Students",
            "Total Mappings Generated",
            "Average Travel Distance (km)",
            "Maximum Travel Distance (km)",
            "Report Generated At"
        ],
        "Value": [
            total_vol,
            total_stud,
            total_assigned,
            unassigned_stud,
            len(assignments),
            avg_dist,
            max_dist,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
    }
    df_summary = pd.DataFrame(summary_data)
    
    # 2. Detailed assignments formatting
    # Keep key columns
    if not df_assignments.empty:
        df_assigned_details = df_assignments[[
            "volunteer_id", "volunteer_name", "student_id", "student_name", "distance_km", "duration_minutes"
        ]].copy()
        df_assigned_details.columns = [
            "Volunteer ID", "Volunteer Name", "Student ID", "Student Name", "Distance (Road km)", "Duration (Minutes)"
        ]
    else:
        df_assigned_details = pd.DataFrame(columns=[
            "Volunteer ID", "Volunteer Name", "Student ID", "Student Name", "Distance (Road km)", "Duration (Minutes)"
        ])
        
    # 3. Unassigned Students
    assigned_stud_ids = set(df_assignments["student_id"].tolist()) if not df_assignments.empty else set()
    unassigned_stud_list = [s for s in students if str(s["id"]) not in assigned_stud_ids]
    if unassigned_stud_list:
        df_unassigned_stud = pd.DataFrame(unassigned_stud_list)[[
            "id", "name", "address", "phone"
        ]].copy()
        df_unassigned_stud.columns = ["Student ID", "Student Name", "Address", "Phone"]
    else:
        df_unassigned_stud = pd.DataFrame(columns=["Student ID", "Student Name", "Address", "Phone"])
        
    # 4. Unassigned Volunteers (0 matches)
    assigned_vol_ids = set(df_assignments["volunteer_id"].tolist()) if not df_assignments.empty else set()
    unassigned_vol_list = [v for v in volunteers if str(v["id"]) not in assigned_vol_ids]
    if unassigned_vol_list:
        df_unassigned_vol = pd.DataFrame(unassigned_vol_list)[[
            "id", "name", "address", "phone"
        ]].copy()
        df_unassigned_vol.columns = ["Volunteer ID", "Volunteer Name", "Address", "Phone"]
    else:
        df_unassigned_vol = pd.DataFrame(columns=["Volunteer ID", "Volunteer Name", "Address", "Phone"])

    # Create memory buffer
    output_buffer = io.BytesIO()
    
    # Write to Excel using xlsxwriter for formatting
    with pd.ExcelWriter(output_buffer, engine="xlsxwriter") as writer:
        df_summary.to_excel(writer, sheet_name="Summary Dashboard", index=False)
        df_assigned_details.to_excel(writer, sheet_name="Volunteer-Student Mappings", index=False)
        df_unassigned_stud.to_excel(writer, sheet_name="Unassigned Students", index=False)
        df_unassigned_vol.to_excel(writer, sheet_name="Unassigned Volunteers", index=False)
        
        # Get xlsxwriter workbook & worksheet objects
        workbook = writer.book
        
        # Styles
        header_format = workbook.add_format({
            "bold": True,
            "text_wrap": True,
            "valign": "top",
            "fg_color": "#2D3748",
            "font_color": "#FFFFFF",
            "border": 1
        })
        
        # Format sheets
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            # Write headers manually to apply style
            df_to_use = (
                df_summary if sheet_name == "Summary Dashboard"
                else df_assigned_details if sheet_name == "Volunteer-Student Mappings"
                else df_unassigned_stud if sheet_name == "Unassigned Students"
                else df_unassigned_vol
            )
            
            for col_num, value in enumerate(df_to_use.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Auto-fit columns
            for i, col in enumerate(df_to_use.columns):
                max_len = max(
                    df_to_use[col].astype(str).map(len).max(),
                    len(str(col))
                ) + 3
                worksheet.set_column(i, i, min(max_len, 50))
                
    output_buffer.seek(0)
    
    filename = f"volunteer_student_mapping_{datetime.now().strftime('%Y%md_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        output_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
