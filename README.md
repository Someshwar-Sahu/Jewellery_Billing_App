# Jewellery Billing App

A complete billing and business management system built for Indian jewellery shops. Handles GST-compliant invoicing, gold/silver rate management, inventory tracking, party ledgers, and financial reporting — all from a web browser with offline-capable PWA support.

---

## Screenshots

### Dashboard
<!-- Upload screenshot: drag and drop image here while editing on GitHub -->
<img width="1920" height="1080" alt="Screenshot 2026-05-13 005728" src="https://github.com/user-attachments/assets/1870dfc1-d555-4a96-9ea7-5034a6097ccf" />

### Create Invoice
<!-- Upload screenshot: drag and drop image here while editing on GitHub -->
<img width="1920" height="1080" alt="Screenshot 2026-05-13 005941" src="https://github.com/user-attachments/assets/ff0d0469-4233-4624-90ad-ca6e405aa20c" />

### Bill Print Preview
<!-- Upload screenshot: drag and drop image here while editing on GitHub -->
<img width="669" height="952" alt="Screenshot 2026-05-13 010144" src="https://github.com/user-attachments/assets/8977aac9-9f67-41c1-9937-f2c3a08e9352" />

### GST Report
<!-- Upload screenshot: drag and drop image here while editing on GitHub -->
<img width="1920" height="1080" alt="Screenshot 2026-05-13 010231" src="https://github.com/user-attachments/assets/3b220ab5-9dc7-41fe-9753-d028164c9ef9" />

---

## Table of Contents

- [Screenshots](#screenshots)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Setup (SQLite)](#local-setup-sqlite)
  - [Production Setup (PostgreSQL + Supabase)](#production-setup-postgresql--supabase)
- [Deployment on Render](#deployment-on-render)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [PWA Support](#pwa-support)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)

---

## Features

### Billing & Invoicing
- Create GST-compliant sale and purchase invoices with automatic tax calculation (CGST/SGST for intrastate, IGST for interstate)
- Support for multiple payment modes: cash, card, UPI, cheque, NEFT
- Credit bill management with due dates and payment tracking
- Invoice edit history with version tracking (full audit log of every change)
- Cancel and recover bills with reason tracking
- Duplicate an existing invoice to speed up repeat billing
- Print-ready bill templates — A4 and small/thermal formats
- Amount-in-words auto-generated on bills (e.g., "Rupees Five Thousand Only")
- Old gold exchange value deducted directly on invoices

### AI-Powered Bill Scanning
- Photograph a handwritten bill and extract all fields automatically using Google Gemini Vision
- Extracted data populates the invoice form — reduce manual data entry for old paper records
- Requires a Google API key (optional feature, app works fully without it)

### Gold & Silver Rate Management
- Set daily rates for Gold 22K, Gold 18K, and Silver per gram
- Rates auto-fill into the invoice creation form when you open it
- Last 30 days of rate history visible at a glance

### Party Management
- Maintain a customer and supplier directory with GSTIN, phone, address
- Per-party ledger showing all invoices, outstanding dues, and advance balance
- Credit and debit tracking per party

### Old Gold / Silver Exchange
- Record old gold and silver received from customers (exchange or direct purchase)
- Track metal type, purity, weight, and value
- Linked to party records for full history

### Advance Payments
- Record advance amounts received from customers before a bill is made
- Advances visible on the party detail page and deductible during billing

### Inventory & Stock
- Product catalogue with purity, category, and low-stock threshold
- Stock ledger: every bill in/out automatically creates a stock entry
- Stock summary with current balance and low-stock alerts
- Manual stock adjustments with notes

### Expense Tracking
- Log business expenses by category (rent, labour, purchase, miscellaneous, etc.)
- Soft-delete with restore support (no data is permanently lost)
- Expense list filterable by financial year and category

### GST Reports
- GSTR-1 report: outward supply summary broken down by HSN and tax rate
- GSTR-3B report: monthly tax liability summary
- GST status workflow: mark invoices as Pending Review → GST Ready → Locked
- Month-level locking to prevent accidental edits after filing

### Excel Exports
- Export invoices, parties, stock ledger, and expenses to formatted `.xlsx` files
- Exports styled with headers, borders, and rupee formatting — ready to share

### Dashboard
- Today's sales count and total
- This month's sales with payment mode breakdown
- Pending dues and low-stock alerts
- Monthly revenue bar chart for the active financial year

### Financial Year Management
- Create and switch between financial years (e.g., 2024–25, 2025–26)
- All reports, invoices, and exports are scoped to the selected financial year
- Close a financial year to lock it permanently

### Shop Settings
- Configure shop name, GSTIN, address, state, phone, and email
- Bank details for printing on bills
- Choose bill print template (A4 or small)

### Authentication
- Single-user login with password protection
- First-run setup wizard to configure shop and credentials
- Session-based auth with secure cookies

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI |
| Templating | Jinja2 (server-side HTML) |
| Database ORM | SQLModel (SQLAlchemy + Pydantic) |
| Migrations | Alembic |
| Database | SQLite (local) / PostgreSQL via Supabase (production) |
| Frontend | Vanilla JS, HTML5, CSS3 |
| PWA | Web App Manifest + Service Worker |
| Excel Export | openpyxl |
| AI Scanning | Google Gemini Vision API |
| Deployment | Render (free tier, Singapore region) |

---

## Project Structure

```
Jewellery_Billing_App/
└── backend/
    ├── app/
    │   ├── main.py              # FastAPI app, middleware, router registration
    │   ├── config.py            # Settings loaded from .env
    │   ├── database.py          # DB engine and session
    │   ├── dependencies.py      # Auth dependency (require_login)
    │   ├── models/              # SQLModel table definitions
    │   │   ├── invoices.py
    │   │   ├── parties.py
    │   │   ├── inventory.py
    │   │   ├── products.py
    │   │   ├── payments.py
    │   │   ├── expenses.py
    │   │   ├── shop.py
    │   │   └── system.py
    │   ├── routers/             # One file per feature area
    │   │   ├── invoices.py
    │   │   ├── parties.py
    │   │   ├── rates.py
    │   │   ├── old_gold.py
    │   │   ├── products.py
    │   │   ├── expenses.py
    │   │   ├── stocks.py
    │   │   ├── advances.py
    │   │   ├── settings.py
    │   │   ├── scan.py
    │   │   ├── reports.py
    │   │   ├── exports.py
    │   │   ├── dashboard.py
    │   │   └── auth.py
    │   ├── schemas/             # Pydantic request/response models
    │   ├── services/            # Business logic (invoice_service, party_service)
    │   ├── static/
    │   │   ├── css/             # App styles and patches
    │   │   ├── js/              # invoice.js, ui.js
    │   │   ├── icons/           # PWA icons
    │   │   ├── manifest.json
    │   │   └── sw.js
    │   └── templates/           # Jinja2 HTML templates
    ├── alembic/                 # DB migration scripts
    ├── alembic.ini
    ├── requirements.txt
    ├── render.yaml              # One-click Render deployment config
    └── .env.example             # Template for environment variables
```

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- `pip`
- Git

### Local Setup (SQLite)

This is the quickest way to run the app on your machine. No external database needed.

**Step 1 — Clone the repository**

```bash
git clone https://github.com/your-username/jewellery-billing-app.git
cd jewellery-billing-app/backend
```

**Step 2 — Create and activate a virtual environment**

```bash
python -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

**Step 3 — Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 4 — Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and set the following (minimum required for local use):

```env
DATABASE_URL=sqlite:///./jewellery.db
SECRET_KEY=any-random-string-here
```

**Step 5 — Run database migrations**

```bash
alembic upgrade head
```

**Step 6 — Start the server**

```bash
uvicorn app.main:app --reload
```

Open your browser and go to `http://localhost:8000`. The setup wizard will guide you through creating your shop profile and login credentials on first run.

---

### Production Setup (PostgreSQL + Supabase)

For a real deployment, use PostgreSQL hosted on [Supabase](https://supabase.com) (free tier available).

**Step 1 — Create a Supabase project**

Go to [supabase.com](https://supabase.com), create a new project, and get your database connection string from:

`Project Settings → Database → Connection string → URI mode`

Use the **Transaction pooler** URL (port `6543`) — required for Render's free tier.

**Step 2 — Update your `.env`**

```env
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
SECRET_KEY=generate-with-python-c-import-secrets-print-secrets-token-hex-32
```

To generate a secure `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Step 3 — Run migrations against the remote DB**

```bash
alembic upgrade head
```

---

## Deployment on Render

The repository includes a `render.yaml` for one-click deployment.

**Step 1** — Push your code to GitHub.

**Step 2** — Go to [render.com](https://render.com) → New → Blueprint → connect your GitHub repo.

**Step 3** — Render will detect `render.yaml` automatically. Set the following environment variables manually in the Render dashboard (do **not** put them in the file):

| Variable | Description |
|---|---|
| `DATABASE_URL` | Your Supabase PostgreSQL connection string |
| `SECRET_KEY` | A strong random 64-character hex string |
| `GOOGLE_API_KEY` | *(Optional)* Only needed for the Scan Bill feature |

**Step 4** — Deploy. Alembic migrations run automatically on every deploy.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | SQLite path or PostgreSQL URI |
| `SECRET_KEY` | Yes | Secret key for session signing |
| `APP_NAME` | No | Display name (default: `Jewellery Billing App`) |
| `GOOGLE_API_KEY` | No | Google Gemini API key for bill scanning |

Never commit your `.env` file. It is listed in `.gitignore`.

---

## Database Migrations

Alembic is used for all schema changes. The migration history is in `backend/alembic/versions/`.

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Create a new migration after modifying models
alembic revision --autogenerate -m "describe_your_change"
```

Migrations are safe to run multiple times — Alembic tracks applied versions and skips already-applied ones.

---

## PWA Support

The app is a Progressive Web App. On Chrome (Android or desktop), users will see an "Add to Home Screen" / "Install" prompt. Once installed:

- The app opens in standalone mode (no browser chrome)
- PWA shortcuts for "New Bill" and "Gold Rates" are available from the app icon
- A service worker (`sw.js`) is registered at the root scope

Icons are located at `backend/app/static/icons/` (192×192 and 512×512 PNG).

---

## Known Limitations

- **Single-user only** — there is one set of credentials per installation. Multi-user / role-based access is not implemented.
- **No real-time sync** — the app does not push live updates across browser tabs.
- **Scan Bill feature requires internet** — it calls the Google Gemini API and will not work offline or without a valid `GOOGLE_API_KEY`.
- **Render free tier spins down** after 15 minutes of inactivity. The first request after idle may take 30–60 seconds to respond.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a pull request

---

*Built for Indian jewellery shops. Handles GST, gold rates, and everything in between.*
