# Ready Roofers – Weather History Report Tool

Standalone web application that generates professional severe-weather history reports for a given property address. Designed for roofing sales teams to support insurance claim conversations.

## Features

- Clean, professional report layout closely matching commercial weather-report samples
- Address → official NOAA/SPC severe weather events (hail > 1", wind > 60 mph)
- 12-month lookback, 10-mile radius
- Sales representative contact customization on every report
- PDF-ready (Print / Save as PDF)
- Shareable link + QR code so a homeowner can open the report on their phone
- “Email to Customer” one-click (opens mail client with link)
- 100% public data sources (no paid weather APIs)

## Data Sources

- **NOAA / Storm Prediction Center (SPC) Severe Weather Database** – official hail and damaging-wind reports compiled from National Weather Service Storm Data.
- **OpenStreetMap Nominatim** – free geocoding.

Official storm reports lag real-time by weeks to a few months; the tool always uses the latest published annual files.

## Quick Start (Local)

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python run.py
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000

## Production Deployment

The app is a standard FastAPI service. Deploy to any platform that supports Python:

- **Render / Railway / Fly.io / DigitalOcean App Platform** – point to this repo, set start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Docker** (example Dockerfile can be added on request)
- Behind your own domain with a reverse proxy (Caddy / Nginx)

For higher volume:

- Replace the in-memory `REPORT_STORE` with Redis or a small database.
- Cache the SPC CSV data more aggressively or load only the needed geographic subset.
- Add authentication if you want the tool internal-only.

## Updating Weather Data

SPC publishes annual CSVs. To refresh:

1. Download the newest `YYYY_hail.csv` and `YYYY_wind.csv` from  
   https://www.spc.noaa.gov/wcm/#data
2. Place them in the `data/` folder.
3. Restart the service (the loader reads whatever year files are present).

## Configuration Notes

- Filters are hard-coded in `app/data_loader.py` (hail > 1.00", wind ≥ 60 mph, 10 mi, 365 days). Easy to adjust.
- Severity scoring mirrors common industry thresholds used in the sample report style.
- Map imagery currently uses a free OpenStreetMap static endpoint. For higher-quality satellite imagery you can later swap in Mapbox or Google Static Maps with an API key.

## License / Disclaimer

This tool is for internal sales enablement and informational use. It is not a certified meteorological or engineering product. Always include the disclaimer shown on the generated reports.
