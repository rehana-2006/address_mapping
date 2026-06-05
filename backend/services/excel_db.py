import os
import threading
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any, Optional
from config import DATABASE_EXCEL_PATH

# Thread safety lock for Excel I/O
_db_lock = threading.Lock()

SHEET_SCHEMAS = {
    "volunteers": ["id", "name", "address", "phone", "latitude", "longitude", "other_details"],
    "students": ["id", "name", "address", "phone", "latitude", "longitude", "other_details"],
    "coordinates": ["address", "latitude", "longitude", "created_at"],
    "distance_matrix": ["volunteer_id", "student_id", "distance_km", "duration_minutes", "updated_at"],
    "assignments": ["volunteer_id", "volunteer_name", "student_id", "student_name", "distance_km", "duration_minutes", "assigned_at"],
    "uploads": ["upload_id", "filename", "file_type", "row_count", "uploaded_at"]
}

def init_db():
    """Initializes the Excel Database file with appropriate sheets and headers if not exists."""
    with _db_lock:
        if DATABASE_EXCEL_PATH.exists():
            # If exists, verify all sheets are present
            try:
                with pd.ExcelFile(DATABASE_EXCEL_PATH) as xls:
                    existing_sheets = xls.sheet_names
            except Exception:
                existing_sheets = []
            
            missing_sheets = [s for s in SHEET_SCHEMAS.keys() if s not in existing_sheets]
            if not missing_sheets:
                return

            # Read existing sheets and add missing ones
            writer = pd.ExcelWriter(DATABASE_EXCEL_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace")
            for sheet in missing_sheets:
                df = pd.DataFrame(columns=SHEET_SCHEMAS[sheet])
                df.to_excel(writer, sheet_name=sheet, index=False)
            writer.close()
        else:
            # Create a new workbook
            writer = pd.ExcelWriter(DATABASE_EXCEL_PATH, engine="openpyxl")
            for sheet, columns in SHEET_SCHEMAS.items():
                df = pd.DataFrame(columns=columns)
                df.to_excel(writer, sheet_name=sheet, index=False)
            writer.close()

class ExcelDB:
    @staticmethod
    def read_sheet(sheet_name: str) -> List[Dict[str, Any]]:
        """Reads all rows from a specific sheet as a list of dicts."""
        init_db()
        with _db_lock:
            try:
                # Read all columns as string to avoid dropping leading zeros in phone numbers or converting IDs to floats
                df = pd.read_excel(DATABASE_EXCEL_PATH, sheet_name=sheet_name, dtype=str)
                # Replace NaN with empty string
                df = df.fillna("")
                return df.to_dict(orient="records")
            except Exception as e:
                print(f"Error reading sheet {sheet_name}: {e}")
                return []

    @staticmethod
    def write_sheet(sheet_name: str, records: List[Dict[str, Any]]) -> bool:
        """Overwrites the content of a specific sheet with the given records."""
        init_db()
        with _db_lock:
            try:
                # Ensure the sheet has the required columns
                columns = SHEET_SCHEMAS.get(sheet_name, [])
                df = pd.DataFrame(records, columns=columns)
                df = df.fillna("")
                
                # We need to write back while preserving other sheets
                # Read all other sheets first
                all_sheets = {}
                with pd.ExcelFile(DATABASE_EXCEL_PATH) as xls:
                    for name in xls.sheet_names:
                        if name != sheet_name:
                            all_sheets[name] = pd.read_excel(xls, sheet_name=name, dtype=str).fillna("")
                
                # Write everything back
                with pd.ExcelWriter(DATABASE_EXCEL_PATH, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    for name, other_df in all_sheets.items():
                        other_df.to_excel(writer, sheet_name=name, index=False)
                return True
            except Exception as e:
                print(f"Error writing to sheet {sheet_name}: {e}")
                return False

    @staticmethod
    def append_rows(sheet_name: str, new_records: List[Dict[str, Any]]) -> bool:
        """Appends new records to a specific sheet."""
        if not new_records:
            return True
        existing = ExcelDB.read_sheet(sheet_name)
        # Filter fields based on schema
        schema_cols = SHEET_SCHEMAS.get(sheet_name, [])
        filtered_records = []
        for r in new_records:
            filtered_r = {}
            for col in schema_cols:
                filtered_r[col] = str(r.get(col, ""))
            filtered_records.append(filtered_r)
            
        combined = existing + filtered_records
        return ExcelDB.write_sheet(sheet_name, combined)

    @staticmethod
    def get_coordinate_cache() -> Dict[str, tuple]:
        """Loads and returns the coordinates cache mapping Address -> (Lat, Lon)."""
        rows = ExcelDB.read_sheet("coordinates")
        cache = {}
        for r in rows:
            addr = r.get("address", "").strip().lower()
            if addr and r.get("latitude") and r.get("longitude"):
                try:
                    cache[addr] = (float(r["latitude"]), float(r["longitude"]))
                except ValueError:
                    pass
        return cache

    @staticmethod
    def cache_coordinate(address: str, lat: float, lon: float):
        """Caches a geocoding result."""
        addr_clean = address.strip().lower()
        cache = ExcelDB.get_coordinate_cache()
        if addr_clean not in cache:
            record = {
                "address": address.strip(),
                "latitude": str(lat),
                "longitude": str(lon),
                "created_at": datetime.now().isoformat()
            }
            ExcelDB.append_rows("coordinates", [record])

    @staticmethod
    def get_distance_cache() -> Dict[str, Dict[str, Any]]:
        """Loads and returns distance cache mapping 'vol_id:stud_id' -> {'distance_km': float, 'duration_minutes': float}."""
        rows = ExcelDB.read_sheet("distance_matrix")
        cache = {}
        for r in rows:
            v_id = r.get("volunteer_id", "")
            s_id = r.get("student_id", "")
            if v_id and s_id:
                try:
                    cache[f"{v_id}:{s_id}"] = {
                        "distance_km": float(r["distance_km"]),
                        "duration_minutes": float(r["duration_minutes"])
                    }
                except ValueError:
                    pass
        return cache

    @staticmethod
    def cache_distances(distances: List[Dict[str, Any]]):
        """Appends distances to the distance matrix sheet, updating duplicate keys."""
        existing = ExcelDB.read_sheet("distance_matrix")
        # Build mapping of existing records to easily update
        matrix_map = {f"{r['volunteer_id']}:{r['student_id']}": r for r in existing if r.get('volunteer_id') and r.get('student_id')}
        
        now_str = datetime.now().isoformat()
        for d in distances:
            key = f"{d['volunteer_id']}:{d['student_id']}"
            matrix_map[key] = {
                "volunteer_id": str(d["volunteer_id"]),
                "student_id": str(d["student_id"]),
                "distance_km": str(d["distance_km"]),
                "duration_minutes": str(d["duration_minutes"]),
                "updated_at": now_str
            }
            
        ExcelDB.write_sheet("distance_matrix", list(matrix_map.values()))

# Run initialization on import
init_db()
