"""
Load and filter official SPC severe weather database CSVs (public domain).
Filters: last 12 months, 10-mile radius, hail > 1.00", wind > 60 mph.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Conversion: SPC wind magnitude is in knots
KNOTS_TO_MPH = 1.15077945


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load_spc_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load 2024 + 2025 hail and wind CSVs into cleaned DataFrames."""
    hail_frames = []
    wind_frames = []

    for year in (2024, 2025):
        hail_path = DATA_DIR / f"{year}_hail.csv"
        wind_path = DATA_DIR / f"{year}_wind.csv"
        if hail_path.exists():
            df = pd.read_csv(hail_path, low_memory=False)
            df["event_type"] = "Hail"
            hail_frames.append(df)
        if wind_path.exists():
            df = pd.read_csv(wind_path, low_memory=False)
            df["event_type"] = "Wind"
            wind_frames.append(df)

    hail = pd.concat(hail_frames, ignore_index=True) if hail_frames else pd.DataFrame()
    wind = pd.concat(wind_frames, ignore_index=True) if wind_frames else pd.DataFrame()

    # Normalize common columns
    for df in (hail, wind):
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["slat"] = pd.to_numeric(df["slat"], errors="coerce")
        df["slon"] = pd.to_numeric(df["slon"], errors="coerce")
        df["mag"] = pd.to_numeric(df["mag"], errors="coerce")

    # Wind: convert knots → mph and keep only meaningful reports
    if not wind.empty:
        wind["mag_mph"] = wind["mag"] * KNOTS_TO_MPH
        wind = wind[wind["mag_mph"].notna() & (wind["mag_mph"] > 0)]
    else:
        wind["mag_mph"] = pd.Series(dtype=float)

    # Hail: keep mag as inches
    if not hail.empty:
        hail["mag_inches"] = hail["mag"]
        hail = hail[hail["mag_inches"].notna() & (hail["mag_inches"] > 0)]
    else:
        hail["mag_inches"] = pd.Series(dtype=float)

    return hail, wind


def severity_for_hail(inches: float) -> tuple[str, int]:
    """Return (label, score) roughly matching common industry / sample grading."""
    if inches >= 2.0:
        return "Severe", 4
    if inches >= 1.5:
        return "Significant", 3
    if inches >= 1.0:
        return "Moderate", 2
    return "Minimal", 1


def severity_for_wind(mph: float) -> tuple[str, int]:
    if mph >= 80:
        return "Severe", 4
    if mph >= 70:
        return "Significant", 3
    if mph >= 60:
        return "Moderate", 2
    return "Minimal", 1


def query_events(
    lat: float,
    lon: float,
    lookback_days: int = 365,
    radius_miles: float = 10.0,
    min_hail_inches: float = 1.01,  # strictly > 1"
    min_wind_mph: float = 60.0,
) -> list[dict[str, Any]]:
    """
    Return filtered, sorted event list (most recent first).
    Each event dict is ready for the report template.
    """
    hail_df, wind_df = load_spc_data()
    # Naive datetime for comparison with pandas (which is also naive)
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    # Convert to pandas Timestamp for reliable comparison
    cutoff_ts = pd.Timestamp(cutoff)

    events: list[dict[str, Any]] = []

    # --- Hail ---
    if not hail_df.empty:
        h = hail_df[
            (hail_df["date"] >= cutoff_ts)
            & (hail_df["mag_inches"] > min_hail_inches)
            & hail_df["slat"].notna()
            & hail_df["slon"].notna()
        ].copy()
        if not h.empty:
            # Vectorized approximate distance filter first (fast bounding box)
            lat_delta = radius_miles / 69.0
            lon_delta = radius_miles / (69.0 * max(0.2, abs(math.cos(math.radians(lat)))))
            h = h[
                (h["slat"] >= lat - lat_delta)
                & (h["slat"] <= lat + lat_delta)
                & (h["slon"] >= lon - lon_delta)
                & (h["slon"] <= lon + lon_delta)
            ]
            for _, row in h.iterrows():
                dist = haversine_miles(lat, lon, float(row["slat"]), float(row["slon"]))
                if dist > radius_miles:
                    continue
                sev_label, sev_score = severity_for_hail(float(row["mag_inches"]))
                events.append(
                    {
                        "date": row["date"].strftime("%d %b %Y") if pd.notna(row["date"]) else "Unknown",
                        "datetime_utc": row["date"].isoformat() if pd.notna(row["date"]) else None,
                        "event_type": "Hail",
                        "magnitude": f'{row["mag_inches"]:.2f}" hail',
                        "magnitude_raw": float(row["mag_inches"]),
                        "severity": sev_label,
                        "score": sev_score,
                        "distance_miles": round(dist, 1),
                        "state": str(row.get("st", "")),
                        "source": "SPC / NWS Storm Data",
                        "lat": float(row["slat"]),
                        "lon": float(row["slon"]),
                        "description": f'Hail of {row["mag_inches"]:.2f}" reported near this location (SPC official storm report).',
                    }
                )

    # --- Wind ---
    if not wind_df.empty:
        w = wind_df[
            (wind_df["date"] >= cutoff_ts)
            & (wind_df["mag_mph"] >= min_wind_mph)
            & wind_df["slat"].notna()
            & wind_df["slon"].notna()
        ].copy()
        if not w.empty:
            lat_delta = radius_miles / 69.0
            lon_delta = radius_miles / (69.0 * max(0.2, abs(math.cos(math.radians(lat)))))
            w = w[
                (w["slat"] >= lat - lat_delta)
                & (w["slat"] <= lat + lat_delta)
                & (w["slon"] >= lon - lon_delta)
                & (w["slon"] <= lon + lon_delta)
            ]
            for _, row in w.iterrows():
                dist = haversine_miles(lat, lon, float(row["slat"]), float(row["slon"]))
                if dist > radius_miles:
                    continue
                mph = float(row["mag_mph"])
                sev_label, sev_score = severity_for_wind(mph)
                mt = str(row.get("mt", "") or "")
                events.append(
                    {
                        "date": row["date"].strftime("%d %b %Y") if pd.notna(row["date"]) else "Unknown",
                        "datetime_utc": row["date"].isoformat() if pd.notna(row["date"]) else None,
                        "event_type": "Wind",
                        "magnitude": f"{mph:.1f} mph",
                        "magnitude_raw": mph,
                        "severity": sev_label,
                        "score": sev_score,
                        "distance_miles": round(dist, 1),
                        "state": str(row.get("st", "")),
                        "source": "SPC / NWS Storm Data",
                        "lat": float(row["slat"]),
                        "lon": float(row["slon"]),
                        "description": f"Wind gust of {mph:.1f} mph reported near this location (SPC official storm report{', ' + mt if mt else ''}).",
                    }
                )

    # Sort most recent first, then by severity
    events.sort(key=lambda e: (e.get("datetime_utc") or "", e.get("score", 0)), reverse=True)
    return events


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    wind_count = sum(1 for e in events if e["event_type"] == "Wind")
    hail_count = sum(1 for e in events if e["event_type"] == "Hail")
    max_sev = max((e["score"] for e in events), default=0)
    label_map = {4: "Severe", 3: "Significant", 2: "Moderate", 1: "Minimal", 0: "None"}
    return {
        "total": len(events),
        "wind": wind_count,
        "hail": hail_count,
        "max_severity": label_map.get(max_sev, "None"),
        "max_score": max_sev,
    }
