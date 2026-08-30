import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class RoutingService:
    @staticmethod
    async def get_route(src_lat: float, src_lng: float, dest_lat: float, dest_lng: float) -> Optional[Dict[str, Any]]:
        """
        Fetches the driving route from OSRM between two coordinates.
        Returns a dictionary with distance_km, eta_minutes, and geometry (GeoJSON).
        If the request fails, returns None (allowing callers to fallback to Haversine).
        """
        try:
            # OSRM expects coordinates in lng,lat order
            url = f"http://router.project-osrm.org/route/v1/driving/{src_lng},{src_lat};{dest_lng},{dest_lat}"
            params = {
                "overview": "full",
                "geometries": "geojson"
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, params=params)
                
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    distance_m = route.get("distance", 0)
                    duration_s = route.get("duration", 0)
                    geometry = route.get("geometry")
                    
                    return {
                        "distance_km": distance_m / 1000.0,
                        "eta_minutes": max(1, int(duration_s / 60)),
                        "geometry": geometry
                    }
            else:
                logger.warning(f"OSRM API returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching route from OSRM: {e}")
            
        return None
