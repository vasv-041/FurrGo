# Healthcare Monitoring Assistant 🏥

A production-style **backend-only** REST API built with FastAPI and Python.
This project is designed as a multi-phase development effort; only **Phase 1** is implemented here.

---

## Project Purpose

The Healthcare Monitoring Assistant provides a secure, extensible backend API for:

- AI-assisted health analysis and Q&A (future phase)
- Medication tracking and reminders (future phase)
- Fitness and wearable device integration (future phase)
- Medical document (PDF / image) analysis (future phase)

---

## Architecture

```
healthcare-monitoring-assistant/
├── app/
│   ├── main.py            ← FastAPI application factory
│   ├── core/
│   │   └── config.py      ← Pydantic Settings (env-driven config)
│   ├── api/
│   │   └── routes/
│   │       └── health.py  ← GET /health endpoint
│   ├── models/            ← Database models (Phase 3+)
│   ├── services/          ← Business logic (Phase 2+)
│   └── utils/             ← Shared helpers (Phase 2+)
├── tests/
│   └── test_health.py     ← pytest test suite
├── .env                   ← Local secrets (git-ignored)
├── .env.example           ← Public config template
├── .gitignore
├── requirements.txt
└── README.md
```

> **Backend only.** There is no frontend, no templating engine, and no static file serving.
> The API is consumed by a client (web, mobile, or other service) via HTTP.

---

## Phase Roadmap

| Phase | Feature                          | Status      |
|-------|----------------------------------|-------------|
| 1     | Project structure & health check | ✅ Complete |
| 2     | Gemini AI chatbot (Q&A)          | ✅ Complete |
| 3     | SQLite database & user data      | ✅ Complete |
| 4     | PDF / image analysis             | ✅ Complete (Integrated in Chat) |
| 5     | Medication & fitness integration | 🔜 Planned  |
| 6     | Deployment (Railway / Render)    | 🔜 Planned  |

---

## Multimodal Gemini Chatbot

The Assistant uses the **Gemini API** (`google-genai`) to provide a multimodal chat experience.

You can send:
- **Text only**: e.g., "What is dehydration?"
- **Image + Text**: e.g., Upload a `.png` and ask "Describe the information visible in this image."
- **PDF + Text**: e.g., Upload a `.pdf` report and ask "Summarize this report in simple language."

### Safety Limitations

**This chatbot provides GENERAL HEALTH INFORMATION ONLY.**
It is strictly instructed **NOT** to diagnose diseases, prescribe medication, or act as a substitute for professional medical advice. Every successful response will include a mandatory safety notice.

### Supported Files & Restrictions

- **Allowed Formats:** `.pdf`, `.png`, `.jpg`, `.jpeg`
- **Max File Size:** 10MB (Configurable via `MAX_UPLOAD_SIZE_MB`)
- Uploaded files are processed and then immediately discarded. They are never committed to version control.

---

## Database

This project uses **SQLite** through **SQLAlchemy 2.x**.

The database file is created automatically in `./data/health_ai.db` on server startup.
Database tables are automatically created from the declarative models on startup.

**Never store production secrets, patient medical data in raw format, or uploaded files directly in Git.**

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- pip

---

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd healthcare-monitoring-assistant
```

### 2. Create a virtual environment

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual values (Phase 1 requires none)
```

---

## Running the Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The server will start at **http://127.0.0.1:8000**.

---

## Running Tests

```bash
pytest tests/ -v
```

Expected output for Phase 1:

```
tests/test_health.py::TestHealthEndpoint::test_health_returns_200 PASSED
tests/test_health.py::TestHealthEndpoint::test_health_returns_json PASSED
tests/test_health.py::TestHealthEndpoint::test_health_status_field PASSED
tests/test_health.py::TestHealthEndpoint::test_health_service_field PASSED
tests/test_health.py::TestHealthEndpoint::test_health_response_shape PASSED
tests/test_health.py::TestHealthEndpoint::test_health_no_extra_fields PASSED

6 passed in ...s
```

---

## API Documentation

When the server is running, visit:

| URL                                 | Description              |
|-------------------------------------|--------------------------|
| http://127.0.0.1:8000/docs          | Swagger UI (interactive) |
| http://127.0.0.1:8000/redoc         | ReDoc (read-only)        |
| http://127.0.0.1:8000/openapi.json  | Raw OpenAPI schema       |

---

## Available Endpoints (Phase 1)

### `GET /health`

Returns the service health status.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "service": "Healthcare Monitoring Assistant"
}
```

### `GET /health/database`

Returns the connection status to the database.

**Response** `200 OK`:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## Environment Variables

See [.env.example](.env.example) for the full list of supported variables.

| Variable                    | Default                          | Required | Phase |
|-----------------------------|----------------------------------|----------|-------|
| `APP_NAME`                  | Healthcare Monitoring Assistant  | No       | 1     |
| `APP_VERSION`               | 0.1.0                            | No       | 1     |
| `DEBUG`                     | False                            | No       | 1     |
| `HOST`                      | 127.0.0.1                        | No       | 1     |
| `PORT`                      | 8000                             | No       | 1     |
| `GEMINI_API_KEY`            | *(empty)*                        | Yes      | 3     |
| `GEMINI_MODEL`              | gemini-1.5-flash                 | No       | 3     |
| `DATABASE_URL`              | sqlite:///./data/health_ai.db    | No       | 2     |
| `UPLOAD_DIR`                | uploads                          | No       | 3     |
| `MAX_UPLOAD_SIZE_MB`        | 10                               | No       | 3     |
| `HEALTH_INTEGRATION_API_KEY`| *(empty)*                        | No       | 5     |

---

## Tech Stack

| Tool               | Purpose                     |
|--------------------|-----------------------------|
| Python 3.11+       | Language                    |
| FastAPI            | Web framework               |
| Uvicorn            | ASGI server                 |
| Pydantic Settings  | Environment configuration   |
| pytest             | Testing framework           |
| httpx              | HTTP client (for tests)     |

---

## License

MIT
