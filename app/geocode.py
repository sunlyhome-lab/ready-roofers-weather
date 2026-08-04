"""
Geocoding via Geoapify (free tier).
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"


async def geocode_address(address: str) -> Optional[dict]:
    """
    Return {'lat': float, 'lon': float, 'display_name': str} or None.
    """
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        return None

    params = {
        "text": address,
        "apiKey": api_key,
        "limit": 1,
        "format": "json",
        "filter": "countrycode:us",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(GEOAPIFY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results") or data.get("features") or []
            if not results:
                return None

            # Geoapify can return either "results" or GeoJSON "features"
            item = results[0]
            if "geometry" in item:  # GeoJSON style
                lon, lat = item["geometry"]["coordinates"]
                props = item.get("properties", {})
                display = props.get("formatted") or props.get("address_line1") or address
            else:  # simple results style
                lat = item.get("lat")
                lon = item.get("lon")
                display = item.get("formatted") or item.get("address_line1") or address

            if lat is None or lon is None:
                return None

            return {
                "lat": float(lat),
                "lon": float(lon),
                "display_name": display,
            }
        except Exception:
            return None
