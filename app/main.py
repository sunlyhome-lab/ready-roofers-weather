"""
Ready Roofers Weather History Report Tool
Standalone production-ready FastAPI application.
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import qrcode
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .data_loader import query_events, summarize
from .geocode import geocode_address

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Ready Roofers Weather Report",
    description="Severe weather history reports for insurance claim support (public NOAA/SPC data)",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Simple in-memory store for shareable reports
REPORT_STORE: dict[str, dict[str, Any]] = {}
REPORT_TTL_HOURS = 72


def _make_report_id() -> str:
    return secrets.token_urlsafe(12)


def _cleanup_old_reports() -> None:
    now = datetime.now(timezone.utc)
    to_delete = []
    for rid, data in REPORT_STORE.items():
        created = data.get("_created")
        if created and (now - created).total_seconds() > REPORT_TTL_HOURS * 3600:
            to_delete.append(rid)
    for rid in to_delete:
        REPORT_STORE.pop(rid, None)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"error": None},
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate_report(
    request: Request,
    address: str = Form(...),
    rep_name: str = Form(...),
    rep_title: str = Form("Roofing Consultant"),
    rep_phone: str = Form(""),
    rep_email: str = Form(""),
):
    address = address.strip()
    if len(address) < 8:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": "Please enter a full street address including city and state."},
            status_code=400,
        )

    geo = await geocode_address(address)
    if not geo:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": "Could not locate that address. Please check the spelling and try again."},
            status_code=400,
        )

    events = query_events(geo["lat"], geo["lon"])
    summary = summarize(events)

    report_id = _make_report_id()
    now = datetime.now(timezone.utc)

    report_data = {
        "report_id": report_id,
        "address": address,
        "display_name": geo["display_name"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "events": events,
        "summary": summary,
        "rep": {
            "name": rep_name.strip(),
            "title": rep_title.strip() or "Roofing Consultant",
            "phone": rep_phone.strip(),
            "email": rep_email.strip(),
        },
        "generated_at": now.strftime("%d %b %Y at %H:%M UTC"),
        "data_period": "Last 12 months of available official data",
        "lookback_note": "Data sourced from the official NOAA/SPC Severe Weather Database. Official storm reports typically lag real-time by several weeks to a few months.",
        "_created": now,
    }

    _cleanup_old_reports()
    REPORT_STORE[report_id] = report_data

    return TEMPLATES.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "r": report_data,
            "share_url": str(request.base_url) + f"r/{report_id}",
        },
    )


@app.get("/r/{report_id}", response_class=HTMLResponse)
async def view_shared_report(request: Request, report_id: str):
    data = REPORT_STORE.get(report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found or has expired.")
    return TEMPLATES.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "r": data,
            "share_url": str(request.base_url) + f"r/{report_id}",
            "is_shared": True,
        },
    )


@app.get("/qr/{report_id}")
async def qr_code(report_id: str, request: Request):
    if report_id not in REPORT_STORE:
        raise HTTPException(status_code=404, detail="Report not found")
    url = str(request.base_url) + f"r/{report_id}"
    img = qrcode.make(url, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/api/health")
async def health():
    return {"status": "ok", "reports_in_memory": len(REPORT_STORE)}
