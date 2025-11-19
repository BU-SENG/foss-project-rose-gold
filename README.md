[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/BY41byMO)

# Local Job Connect

A lightweight job board and applicant management web application built with Flask. Local Job Connect helps employers post local job openings and job seekers find, save, and apply to jobs — supporting geocoded locations, resume uploads, and simple dashboards for both employers and job seekers.

---

**Team Members:**
- 22/0098
- 22/0150
- 22/0312
- 22/0309
- 22/0298

---

## Features

- Employer dashboard: create, edit, pause and archive job postings
- Job seeker dashboard: search by keyword/radius, save jobs, apply with uploaded resumes
- Geocoded job locations with distance calculation
- Resume upload and management (PDF only)
- Role-based authentication (employer / job_seeker)

## Tech Stack

- Backend: Python, Flask, Flask-Login, Flask-SQLAlchemy
- Frontend: Jinja2 templates, vanilla JavaScript, responsive CSS
- DB: SQLite by default (configurable via `DATABASE_URL`)
- Geocoding: Mapbox (optional — API token required for address validation)

## Repository Layout

Top-level important folders:

- `backend/` — Flask application, templates, static assets, and `requirements.txt`
	- `backend/app.py` — main Flask application
	- `backend/templates/` — Jinja2 templates
	- `backend/static/` — CSS, JS, uploaded resumes (`static/uploads/resumes`)

## Quickstart — Run locally (Windows / Cross-platform)

Prerequisites:

- Python 3.10+ installed
- Git (to clone the repo)

1. Clone the repo (if you haven't already):

```powershell
git clone <repo-url>
cd "foss-project-rose-gold\backend"
```

2. Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate; pip install -r requirements.txt
```

On macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Create uploads folder (if it doesn't exist):

```powershell
mkdir -Force ..\backend\static\uploads\resumes
```

4. Create a `.env` file in `backend/` with the following variables (example):

```
SECRET_KEY=super-secret-key
DATABASE_URL=sqlite:///instance/local_job_connect.db
MAPBOX_ACCESS_TOKEN=your_mapbox_token_here
SERVICE_AREA_CENTER_LAT=6.5244
SERVICE_AREA_CENTER_LNG=3.3792
SERVICE_AREA_RADIUS_KM=50
```

Notes:
- `DATABASE_URL` can point to a Postgres URL for production. The example uses SQLite for local development.
- `MAPBOX_ACCESS_TOKEN` is required for address geocoding. If not provided, address validation may fail and some flows will show an error.

5. Initialize and run the app (this will create the database tables and start the dev server):

```powershell
python app.py
```

Then open `http://127.0.0.1:5000/` in your browser.

## Usage

- Register as an employer or job seeker using the `Register` page.
- Employers can post jobs from the Employer Dashboard.
- Job seekers can search jobs by keyword, filter by radius, save favorites, upload up to 3 resumes, and apply to open jobs.

## Environment Variables (summary)

- `SECRET_KEY` — Flask session secret.
- `DATABASE_URL` — SQLAlchemy database URI (e.g., `sqlite:///instance/local_job_connect.db` or Postgres URI).
- `MAPBOX_ACCESS_TOKEN` — (optional but recommended) Mapbox token for geocoding addresses.
- `SERVICE_AREA_CENTER_LAT` / `SERVICE_AREA_CENTER_LNG` — center coordinates used to validate job locations.
- `SERVICE_AREA_RADIUS_KM` — maximum allowed distance (in km) from the service center for new job postings.

## Troubleshooting

- Geocoding failures: If address validation fails during registration or job creation, ensure `MAPBOX_ACCESS_TOKEN` is set and valid.
- Database errors: confirm `DATABASE_URL` is correct and that the `instance/` folder is writable.
- File uploads: only PDF files are allowed and the default max upload size is 16 MB.

## Development Notes

- The app creates DB tables automatically on first run (`db.create_all()` in `app.py`). For production deployments, run proper migrations (e.g., Flask-Migrate).
- If you want to run using `flask run`, set the `FLASK_APP` environment variable to `app.py` and export `FLASK_ENV=development` for debug mode.

## Contributing

If you'd like to contribute, please open an issue or create a pull request. Keep changes small and focused and include a description of the problem and how to reproduce it.
