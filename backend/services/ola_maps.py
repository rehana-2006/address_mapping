import httpx
import hashlib
import math
import random
from typing import List, Dict, Any, Optional, Tuple
from config import OLA_MAPS_API_KEY, OLA_MAPS_BASE_URL

class OlaMapsClient:
    def __init__(self):
        self.api_key = OLA_MAPS_API_KEY
        self.base_url = OLA_MAPS_BASE_URL
        self.is_mock = self.api_key == "MOCK" or not self.api_key

    def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocodes an address into (latitude, longitude) using Ola Maps Geocoding API.
        If in mock mode or API fails, uses a deterministic hash-based location around Chennai.
        """
        if not address or not address.strip():
            return None

        # Clean address
        address_clean = address.strip()

        if self.is_mock:
            return self._mock_geocode(address_clean)

        try:
            url = f"{self.base_url}/places/v1/geocode"
            params = {
                "address": address_clean,
                "api_key": self.api_key
            }
            headers = {
                "X-Request-Id": f"geo-{hashlib.md5(address_clean.encode()).hexdigest()[:8]}"
            }
            
            response = httpx.get(url, params=params, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                results = data.get("geocodingResults", [])
                if results:
                    location = results[0].get("geometry", {}).get("location", {})
                    lat = location.get("lat")
                    lng = location.get("lng")
                    if lat is not None and lng is not None:
                        return float(lat), float(lng)
            
            print(f"Ola Maps Geocoding failed (Status {response.status_code}). Falling back to mock geocoder.")
            return self._mock_geocode(address_clean)
        except Exception as e:
            print(f"Ola Maps Geocoding Exception: {e}. Falling back to mock geocoder.")
            return self._mock_geocode(address_clean)

    def get_distance_matrix(self, origins: List[Tuple[str, float, float]], destinations: List[Tuple[str, float, float]]) -> List[Dict[str, Any]]:
        """
        Calculates travel distance (km) and duration (mins) between origins and destinations.
        origins: List of (id, lat, lon)
        destinations: List of (id, lat, lon)
        Returns: List of dicts with volunteer_id, student_id, distance_km, duration_minutes.
        """
        if not origins or not destinations:
            return []

        if self.is_mock:
            return self._mock_distance_matrix(origins, destinations)

        # Batch requests or send a single request if sizes are reasonable.
        # Ola Maps Distance Matrix format: origins=lat,lng|lat,lng&destinations=lat,lng|lat,lng
        results = []
        
        # To avoid exceeding URL length or API limits, we chunk destinations in groups of 10
        dest_chunk_size = 10
        for i in range(0, len(destinations), dest_chunk_size):
            dest_chunk = destinations[i:i + dest_chunk_size]
            
            # Format origins: "lat,lng|lat,lng"
            origins_param = "|".join([f"{lat},{lng}" for _, lat, lng in origins])
            destinations_param = "|".join([f"{lat},{lng}" for _, lat, lng in dest_chunk])
            
            try:
                url = f"{self.base_url}/routing/v1/distanceMatrix"
                params = {
                    "origins": origins_param,
                    "destinations": destinations_param,
                    "api_key": self.api_key
                }
                headers = {
                    "X-Request-Id": f"dist-{random.randint(1000, 9999)}"
                }
                
                response = httpx.get(url, params=params, headers=headers, timeout=15.0)
                if response.status_code == 200:
                    data = response.json()
                    # The response typically has: { "rows": [ { "elements": [ { "distance": 123, "duration": 456 } ] } ] }
                    rows = data.get("rows", [])
                    
                    for o_idx, origin in enumerate(origins):
                        v_id = origin[0]
                        if o_idx >= len(rows):
                            continue
                            
                        elements = rows[o_idx].get("elements", [])
                        for d_idx, dest in enumerate(dest_chunk):
                            s_id = dest[0]
                            if d_idx >= len(elements):
                                continue
                                
                            element = elements[d_idx]
                            
                            # distance in meters -> convert to km
                            dist_meters = element.get("distance", 0)
                            dist_km = round(float(dist_meters) / 1000.0, 2)
                            
                            # duration in seconds -> convert to minutes
                            dur_seconds = element.get("duration", 0)
                            dur_mins = round(float(dur_seconds) / 60.0, 1)
                            
                            # If API returns an error or status was invalid for this element
                            if dist_meters == 0 and dur_seconds == 0:
                                # Fall back to mock distance for this specific element
                                mock_val = self._calculate_haversine_road(origin[1], origin[2], dest[1], dest[2])
                                dist_km = mock_val["distance_km"]
                                dur_mins = mock_val["duration_minutes"]

                            results.append({
                                "volunteer_id": v_id,
                                "student_id": s_id,
                                "distance_km": dist_km,
                                "duration_minutes": dur_mins
                            })
                else:
                    print(f"Ola Maps Distance Matrix failed (Status {response.status_code}). Using mock distances.")
                    results.extend(self._mock_distance_matrix(origins, dest_chunk))
            except Exception as e:
                print(f"Ola Maps Distance Matrix Exception: {e}. Using mock distances.")
                results.extend(self._mock_distance_matrix(origins, dest_chunk))
                
        return results

    def _mock_geocode(self, address: str) -> Tuple[float, float]:
        """
        Generates a deterministic location in the Chennai area based on address string.
        Center: Tambaram/Chennai region (lat=12.9249, lng=80.1000)
        """
        # MD5 hash of address to get a seed
        hash_val = int(hashlib.md5(address.encode("utf-8")).hexdigest(), 16)
        
        # Coordinates center
        # Let's place it around Tambaram, Chennai
        center_lat = 12.9249
        center_lng = 80.1000
        
        # Max offset of ~0.15 degrees (~15 km)
        random.seed(hash_val)
        offset_lat = (random.random() - 0.5) * 0.15
        offset_lng = (random.random() - 0.5) * 0.15
        
        lat = round(center_lat + offset_lat, 6)
        lng = round(center_lng + offset_lng, 6)
        
        return lat, lng

    def _calculate_haversine_road(self, lat1: float, lng1: float, lat2: float, lng2: float) -> Dict[str, float]:
        """Calculates distance between coordinates using Haversine formula + road multiplier."""
        # Radius of the earth in km
        R = 6371.0
        
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        haversine_dist = R * c
        
        # Road distance is typically 1.25 to 1.4 times straight-line distance
        road_dist = haversine_dist * 1.3
        # Ensure at least 0.1 km
        road_dist = max(road_dist, 0.1)
        
        # Duration based on average urban speed of 30 km/h (2 mins per km) + 3 mins buffer
        duration_mins = (road_dist / 30.0) * 60.0 + 3.0
        
        return {
            "distance_km": round(road_dist, 2),
            "duration_minutes": round(duration_mins, 1)
        }

    def _mock_distance_matrix(self, origins: List[Tuple[str, float, float]], destinations: List[Tuple[str, float, float]]) -> List[Dict[str, Any]]:
        """Generates realistic mock road distances/durations between origins and destinations."""
        results = []
        for v_id, v_lat, v_lng in origins:
            for s_id, s_lat, s_lng in destinations:
                road_info = self._calculate_haversine_road(v_lat, v_lng, s_lat, s_lng)
                results.append({
                    "volunteer_id": v_id,
                    "student_id": s_id,
                    "distance_km": road_info["distance_km"],
                    "duration_minutes": road_info["duration_minutes"]
                })
        return results
