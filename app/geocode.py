"""
Free geocoding via OpenStreetMap Nominatim.
Respects usage policy: custom User-Agent, low volume.
"""

from __future__ import annotations

import httpx
from typing import Optional


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ReadyRoofersWeatherReport/1.0 (sales-enablement; contact@readyroofers.example)"


async def geocode_address(address: str) -> Optional[dict]:
    """
    Return {'lat': float, 'lon': float, 'display_name': str} or None.
    """
    params = {
        "q": address,
        "format": "json",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "us",
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return None
            item = data[0]
            return {
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "display_name": item.get("display_name", address),
            }
        except Exception:
            return None
