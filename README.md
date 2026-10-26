# Hadaf Al Nasar

A Flask-based business management system for a UAE (Dubai) logistics and transport company. It combines accounting, invoicing, payroll (WPS), employee management, and shipment/fleet tracking in one web application.

## Features

- **Authentication and security** – login with Flask-Login, bcrypt password hashing, CSRF protection, rate limiting, and security headers middleware.
- **Customers and invoicing** – customer records, invoices with line items, and PDF invoice generation (ReportLab).
- **Income and expenses** – income verification and recording, expense tracking, dashboards, and financial reports.
- **Employees and payroll (WPS)** – employee records, attendance, leave, salary processing, and salary notifications.
- **Logistics** – shipments, drivers, vehicles, and route optimization (Google Maps).
- **Notifications** – email (SMTP) and WhatsApp (Twilio / WhatsApp Business API).
- **UAE integrations** – Dubai Government and Dubai DED company lookups.

## Tech Stack

- Python, Flask 3.1
- SQLAlchemy 2 / Flask-SQLAlchemy / Flask-Migrate (Alembic)
- SQLite for local development, PostgreSQL for production (`psycopg2`)
- Gunicorn for deployment
- Jinja2 templates

## Project Structure

```
.
├── app/
│   ├── models/         # core, finance, logistics, wps models
│   ├── routes/         # auth, customers, invoices, income, expense, employee, salary, transport, reports, dashboard
│   ├── services/       # invoice, income, customer, PDF, WPS services
│   ├── middleware/     # security headers and request security
│   ├── utils/          # helpers, email, WhatsApp, route optimizer, validation
│   ├── templates/      # Jinja2 templates
│   └── static/         # CSS and JS
├── migrations/         # Alembic migrations
├── maintenance_scripts/
├── config.py           # Application configuration
├── main.py             # Local entry point
├── wsgi.py             # WSGI entry point
├── passenger_wsgi.py   # Passenger (shared hosting) entry point
├── start.sh            # Production start script (creates tables, seeds admin, runs Gunicorn)
├── Dockerfile.security # Security scanning image
└── requirements.txt
```

## Getting Started

### Prerequisites

- Python 3.10+
- pip
- (Optional) PostgreSQL for production

### Installation

```bash
git clone https://github.com/Zi-Ai-tech/hadaf_al_nasar.git
cd hadaf_al_nasar

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask secret key (required in production) |
| `DATABASE_URL` | Database connection string; defaults to local SQLite |
| `DEBUG`, `FLASK_APP`, `FLASK_ENV` | Flask runtime settings |
| `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS` | Email sending |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` | WhatsApp via Twilio |
| `WHATSAPP_BUSINESS_ID`, `WHATSAPP_ACCESS_TOKEN` | WhatsApp Business API |
| `GOOGLE_MAPS_API_KEY` | Route optimization |
| `DUBAI_GOV_API_BASE_URL`, `DUBAI_GOV_API_KEY` | Dubai Government API |
| `DUBAI_DED_API_BASE_URL`, `DUBAI_DED_API_KEY` | Dubai DED API |
| `SESSION_COOKIE_SECURE` | Set to `true` when served over HTTPS |
| `MAX_CREDIT_LIMIT`, `ITEMS_PER_PAGE` | Business settings |
| `LOG_TO_STDOUT`, `LOG_LEVEL` | Logging |

> Never commit your `.env` file. It is already listed in `.gitignore`.

### Initialize the Database

```bash
python init_db.py
```

Or, to use migrations:

```bash
flask db upgrade
```

### Run Locally

```bash
python main.py
```

The app will be available at <http://127.0.0.1:5000>, with the login page at `/login`.

## Deployment

The included `start.sh` creates the database tables, seeds an `admin` user if none exists, and starts Gunicorn on `$PORT`:

```bash
bash start.sh
```

**Important:** the seeded admin account uses a default password. Change it immediately after first login, and consider replacing the hardcoded value in `start.sh` with an environment variable.

## Security

- Security scanning is configured in `.github/workflows/security.yml` and `.safety.yml`.
- See `SECURITY_RESPONSE.md` for how security issues are handled.
- Keep all API keys and credentials in environment variables only.

## License

No license has been specified. All rights reserved by the repository owner.
