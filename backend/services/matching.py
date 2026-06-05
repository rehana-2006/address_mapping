from typing import List, Dict, Any

import numpy as np
from scipy.optimize import linear_sum_assignment

class MatchingService:
    @staticmethod
    def generate_assignments(
        volunteers: List[Dict[str, Any]],
        students: List[Dict[str, Any]],
        distance_matrix: Dict[str, Dict[str, Any]],
        max_students: int = 4,
        prevent_duplicates: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Assigns each volunteer to the nearest students based on road distance.
        
        Rules:
        - Configurable max students per volunteer.
        - Configurable duplicate prevention (each student assigned to at most one volunteer).
        - Uses Hungarian algorithm for globally optimal assignment to minimize total distance.
        
        Returns:
        List of assignments, where each assignment is a dict containing volunteer and student details.
        """
        if not volunteers or not students:
            return []

        # Create lookups
        vol_lookup = {str(v["id"]): v for v in volunteers}
        stud_lookup = {str(s["id"]): s for s in students}
        
        assignments = []

        if not prevent_duplicates:
            # Simple approach: For each volunteer, find their top N closest students
            for v in volunteers:
                v_id = str(v["id"])
                
                # Calculate distances to all students
                stud_distances = []
                for s in students:
                    s_id = str(s["id"])
                    cache_key = f"{v_id}:{s_id}"
                    
                    if cache_key in distance_matrix:
                        dist = distance_matrix[cache_key]["distance_km"]
                        dur = distance_matrix[cache_key]["duration_minutes"]
                    else:
                        # Fallback high value if distance not calculated
                        dist = 99999.0
                        dur = 99999.0
                        
                    stud_distances.append((s_id, dist, dur))
                
                # Sort by distance
                stud_distances.sort(key=lambda x: x[1])
                
                # Assign top N
                for s_id, dist, dur in stud_distances[:max_students]:
                    if dist < 99999.0:
                        s = stud_lookup[s_id]
                        assignments.append({
                            "volunteer_id": v_id,
                            "volunteer_name": v["name"],
                            "student_id": s_id,
                            "student_name": s["name"],
                            "distance_km": dist,
                            "duration_minutes": dur
                        })
        else:
            # Prevent duplicate assignments using Hungarian Algorithm (Global Minimum Distance)
            num_volunteers = len(volunteers)
            num_students = len(students)
            
            # Each volunteer has `max_students` slots.
            # We map each slot to the original volunteer.
            slots = []
            for v in volunteers:
                for _ in range(max_students):
                    slots.append(v)
                    
            num_slots = len(slots)
            
            # Create Cost Matrix (rows = slots, cols = students)
            # We initialize with a high cost (99999.0)
            cost_matrix = np.full((num_slots, num_students), 99999.0)
            dur_matrix = np.full((num_slots, num_students), 99999.0)
            
            for i, slot_v in enumerate(slots):
                v_id = str(slot_v["id"])
                for j, s in enumerate(students):
                    s_id = str(s["id"])
                    cache_key = f"{v_id}:{s_id}"
                    if cache_key in distance_matrix:
                        cost_matrix[i, j] = distance_matrix[cache_key]["distance_km"]
                        dur_matrix[i, j] = distance_matrix[cache_key]["duration_minutes"]
                        
            # Run linear_sum_assignment (Hungarian algorithm)
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            
            for r, c in zip(row_ind, col_ind):
                dist = cost_matrix[r, c]
                # Only assign if distance is valid (< 99999.0)
                if dist < 99999.0:
                    v = slots[r]
                    s = students[c]
                    dur = dur_matrix[r, c]
                    
                    assignments.append({
                        "volunteer_id": str(v["id"]),
                        "volunteer_name": v["name"],
                        "student_id": str(s["id"]),
                        "student_name": s["name"],
                        "distance_km": dist,
                        "duration_minutes": dur
                    })
                    
        return assignments
