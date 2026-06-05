from typing import List, Dict, Any

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
        - Sort by shortest road distance.
        - Configurable max students per volunteer.
        - Configurable duplicate prevention (each student assigned to at most one volunteer).
        
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
            # Prevent duplicate assignments.
            # We use a balanced greedy round-robin algorithm:
            # Round 1: Assign each volunteer their closest unassigned student
            # Round 2: Assign each volunteer who has < max_students their next closest unassigned student
            # ... and so on, until all volunteers have max_students, or no students are left.
            
            assigned_students = set()
            vol_assignments = {str(v["id"]): [] for v in volunteers}
            
            for round_num in range(max_students):
                # In each round, we iterate through volunteers and let them choose their closest available student
                for v in volunteers:
                    v_id = str(v["id"])
                    
                    # Find closest available student
                    best_student = None
                    best_dist = 99999.0
                    best_dur = 99999.0
                    
                    for s in students:
                        s_id = str(s["id"])
                        if s_id in assigned_students:
                            continue
                            
                        cache_key = f"{v_id}:{s_id}"
                        if cache_key in distance_matrix:
                            dist = distance_matrix[cache_key]["distance_km"]
                            dur = distance_matrix[cache_key]["duration_minutes"]
                        else:
                            dist = 99999.0
                            dur = 99999.0
                            
                        if dist < best_dist:
                            best_dist = dist
                            best_dur = dur
                            best_student = s_id
                            
                    # If we found an available student, assign them
                    if best_student and best_dist < 99999.0:
                        assigned_students.add(best_student)
                        vol_assignments[v_id].append({
                            "student_id": best_student,
                            "distance_km": best_dist,
                            "duration_minutes": best_dur
                        })
            
            # Format output
            for v_id, matches in vol_assignments.items():
                v = vol_lookup[v_id]
                for match in matches:
                    s = stud_lookup[match["student_id"]]
                    assignments.append({
                        "volunteer_id": v_id,
                        "volunteer_name": v["name"],
                        "student_id": match["student_id"],
                        "student_name": s["name"],
                        "distance_km": match["distance_km"],
                        "duration_minutes": match["duration_minutes"]
                    })
                    
        return assignments
