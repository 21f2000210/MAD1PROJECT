# 🏠 A-Z Household Services Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1.2-black?logo=flask)
![SQLite](https://img.shields.io/badge/Database-SQLite-green?logo=sqlite)
![Bootstrap](https://img.shields.io/badge/UI-Bootstrap%205-purple?logo=bootstrap)
![Claude AI](https://img.shields.io/badge/AI-Claude%20(Anthropic)-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

**A full-stack, multi-role household services marketplace** connecting customers with verified service professionals — built with Flask, SQLAlchemy, and Claude AI.

</div>

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Feature Highlights](#-feature-highlights)
3. [Tech Stack](#-tech-stack)
4. [Project Structure](#-project-structure)
5. [Database Schema](#-database-schema)
6. [Application Roles & Workflows](#-application-roles--workflows)
7. [AI Features (Claude Integration)](#-ai-features-claude-integration)
8. [REST API Documentation](#-rest-api-documentation)
9. [Email Notification System](#-email-notification-system)
10. [Security Implementation](#-security-implementation)
11. [Getting Started](#-getting-started)
12. [Environment Configuration](#-environment-configuration)
13. [Database Setup & Migrations](#-database-setup--migrations)
14. [Running the Application](#-running-the-application)
15. [Creating Test Users](#-creating-test-users)
16. [Using the API](#-using-the-rest-api)
17. [All Routes Reference](#-all-routes-reference)
18. [Dark Mode & UI Features](#-dark-mode--ui-features)

---

## 🌐 Project Overview

**A-Z Household Services** is a production-grade, full-stack web application that functions as a marketplace for household services. It implements a three-role architecture — **Admin**, **Customer**, and **Service Professional** — each with their own dedicated dashboards, workflows, and permissions.

The platform handles the entire service lifecycle:

```
Customer Books → Professional Accepts/Rejects → Customer Reviews → Customer Pays
```

Beyond the core workflow, the app features a **RESTful API**, **AI-powered features** (via Anthropic's Claude), **asynchronous email notifications**, **interactive data charts**, **CSV exports**, **rate limiting**, **dark mode**, and much more — making it a showcase of modern Flask development practices.

---

## ✨ Feature Highlights

### 🔐 Authentication & Authorization
- Secure session-based login using **Flask-Login**
- Password hashing using **Werkzeug's** `generate_password_hash`
- Three distinct user roles: `admin`, `customer`, `professional`
- Custom route-protection decorators (`@admin_required`, `@customer_required`, `@professional_required`)
- Admin can **block/unblock** any user, instantly revoking access
- Professionals must be **admin-verified** before accepting jobs
- CSRF protection on every form via **Flask-WTF**

### 🛠 Admin Dashboard
- **Service CRUD**: Create, view, update, and delete service categories with base pricing
- **Professional Approval**: Review and approve/reject newly registered professionals
- **User Management**: Block or unblock customers and professionals
- **Rejected Request Reassignment**: Admins can reassign a rejected request to a different professional
- **Advanced Search**: Search users by name, email, address, PIN, or service type
- **Interactive Charts**: Live Chart.js visualisations for service-request status distribution and rating distribution
- **CSV Export**: Download all service requests or all users as `.csv` files

### 👤 Customer Portal
- **Professional Discovery**: Browse and search for professionals filtered by service type, location, PIN, name, or description
- **Smart Sorting**: Sort search results by average rating, price (low→high / high→low), or experience
- **Booking System**: Book a professional with a proposed price and requested date
- **Request Management**: Edit pending request prices before they are accepted
- **Service History**: Track all bookings with their current status
- **Review & Rating System**: Rate professionals (1–5 stars) with written remarks after service completion
- **Dummy Payment Flow**: Confirm and process payment after closing a service request

### 🔧 Professional Portal
- **Incoming Requests Dashboard**: See all pending booking requests in real time
- **Accept / Reject Requests**: Handle each request individually
- **Job History**: View all past requests (accepted, rejected, closed, paid)
- **Statistics Summary**: See personal stats — total accepted, completed, and rejected jobs, plus average rating

### 🌍 Public Profiles
- Every professional has a **publicly accessible profile page** showing their service, experience, description, and all customer reviews with star ratings

---

## 🏗 Tech Stack

| Layer | Technology | Version |
|---|---|---|
| **Backend Language** | Python | 3.8+ |
| **Web Framework** | Flask | 3.1.2 |
| **ORM** | Flask-SQLAlchemy / SQLAlchemy | 3.1.1 / 2.0.43 |
| **Database** | SQLite | — |
| **DB Migrations** | Flask-Migrate (Alembic) | 4.1.0 / 1.16.5 |
| **Authentication** | Flask-Login | 0.6.3 |
| **Forms & CSRF** | Flask-WTF / WTForms | 1.2.2 / 3.2.1 |
| **Email** | Flask-Mail | 0.10.0 |
| **Rate Limiting** | Flask-Limiter | 3.9.0 |
| **AI (Claude)** | Anthropic Python SDK | ≥0.40.0 |
| **Frontend Framework** | Bootstrap | 5 (CDN) |
| **Charts** | Chart.js | CDN |
| **Icons** | Font Awesome | 6.5.1 (CDN) |
| **Templating** | Jinja2 | 3.1.6 |
| **Environment Vars** | python-dotenv | 1.1.1 |
| **Password Hashing** | Werkzeug | 3.1.3 |

---

## 📁 Project Structure

```
MAD1PROJECT/
│
├── run.py                          # App entry point + CLI commands
├── config.py                       # All config (DB, mail, AI, rate limits)
├── requirements.txt                # Python dependencies
│
├── app/
│   ├── __init__.py                 # App factory — registers extensions & blueprints
│   ├── models.py                   # 7 SQLAlchemy models
│   ├── forms.py                    # 9 WTForms with custom validators
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py                 # Login, Register, Logout
│   │   ├── admin.py                # Admin dashboard, CRUD, search, export
│   │   ├── customer.py             # Booking, history, review, payment
│   │   ├── professional.py         # Request handling, summary stats
│   │   ├── shared.py               # Public profiles, edit profile
│   │   ├── api.py                  # RESTful API (/api/v1/*)
│   │   └── ai_routes.py            # Claude AI endpoints (/ai/*)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── email_service.py        # Async email notifications (5 templates)
│   │
│   ├── static/
│   │   └── css/
│   │       └── style.css           # Custom styles + dark mode support
│   │
│   └── templates/
│       ├── base.html               # Base layout (dark mode, toasts, AI widget)
│       ├── login.html
│       ├── register.html
│       ├── error.html              # Handles 403, 404, 429
│       ├── _navbar.html            # Role-aware navigation bar
│       │
│       ├── admin/
│       │   ├── admin_dashboard.html
│       │   └── admin_search.html
│       │
│       ├── customer/
│       │   ├── customer_dashboard.html
│       │   ├── customer_profile.html
│       │   ├── service_history.html
│       │   └── payment.html
│       │
│       ├── professional/
│       │   ├── professional_dashboard.html
│       │   └── professional_summary.html
│       │
│       └── shared/
│           ├── edit_profile.html
│           └── professional_profile.html
│
├── migrations/                     # Alembic migration scripts
│   ├── env.py
│   └── versions/
│       ├── d70b981fa9c5_initial_schema_creation.py
│       └── 421a6024d18c_refactored_models_with_indexes_and_.py
│
└── logs/
    └── azhousehold.log             # Application log (production mode)
```

---

## 🗄 Database Schema

The application uses **7 database models** with proper relationships, cascading deletes, indexed columns, and check constraints.

```
┌─────────────────────────────────────┐
│               users                 │
│─────────────────────────────────────│
│ id           PK                     │
│ username     unique, indexed        │
│ email        unique, indexed        │
│ password_hash                       │
│ role         indexed (admin/        │
│              customer/professional) │
│ address      indexed                │
│ pin          indexed                │
│ is_active    default: True          │
│ api_key      unique, indexed        │
│ created_at   UTC timestamp          │
│ updated_at   UTC timestamp          │
└────────────────┬────────────────────┘
                 │ 1:1
     ┌───────────┴──────────────┐
     │                          │
┌────▼──────────┐   ┌──────────▼───────────────┐
│   customers   │   │   service_professionals   │
│───────────────│   │───────────────────────────│
│ id       PK   │   │ id            PK           │
│ user_id  FK   │   │ user_id       FK (unique)  │
│ admin_blocked │   │ service_id    FK, indexed  │
└──────┬────────┘   │ description               │
       │            │ experience (years)         │
       │            │ document (URL)             │
       │            │ is_verified   indexed      │
       │            │ verification_failed        │
       │            │ admin_blocked              │
       │            └──────────┬────────────────┘
       │                       │
       │           ┌───────────┘
       │           │
┌──────▼───────────▼──────────────────┐
│           service_requests          │
│─────────────────────────────────────│
│ id                PK                │
│ service_id        FK, indexed       │
│ customer_id       FK, indexed       │
│ professional_id   FK, nullable      │
│ proposed_price                      │
│ date_of_request   indexed (UTC)     │
│ date_of_completion                  │
│ service_status    ENUM:             │
│   REQUESTED → ACCEPTED/REJECTED     │
│   → CLOSED → PAID                  │
│ remarks                             │
└──────────────────┬──────────────────┘
                   │ 1:1
┌──────────────────▼──────────────────┐
│               reviews               │
│─────────────────────────────────────│
│ id                    PK            │
│ customer_id           FK, indexed   │
│ professional_id       FK, indexed   │
│ service_id            FK, indexed   │
│ service_request_id    FK, unique    │
│ rating                CHECK 1–5     │
│ remarks                             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│              services               │
│─────────────────────────────────────│
│ id           PK                     │
│ service_type unique, indexed        │
│ description                         │
│ base_price                          │
│ image_url                           │
└─────────────────────────────────────┘
```

**Key database decisions:**
- All foreign keys use `ondelete='CASCADE'` — deleting a user removes all their related data automatically
- `service_request_id` in reviews is **unique**, ensuring one review per service request (no duplicate reviews)
- `rating` has a database-level `CHECK` constraint ensuring values are always between 1 and 5
- All timestamp fields are **timezone-aware UTC** for consistency across environments
- Indexes placed on all frequently searched/joined columns for query performance

---

## 👥 Application Roles & Workflows

### Role 1 — Admin

The admin is the platform owner/operator.

**Capabilities:**
```
Login as Admin
│
├── Manage Services
│   ├── Create new service category (name, base price, description)
│   ├── Update existing service details
│   └── Delete service (blocked if professionals are assigned to it)
│
├── Manage Professionals
│   ├── View all pending (unverified) professionals
│   ├── Approve professional → they can now accept jobs
│   └── Reject professional → marked as verification_failed
│
├── Manage Users
│   ├── Block user → they cannot log in
│   └── Unblock user → access restored
│
├── Manage Requests
│   └── Reassign rejected requests to a different professional
│
├── Search
│   └── Multi-parameter user search (name, email, address, PIN, service)
│
├── Data Insights
│   ├── Chart: Service request status distribution (pie/bar)
│   └── Chart: Rating distribution (1–5 stars)
│
└── Export Data
    ├── Export all service requests as CSV
    └── Export all users as CSV
```

---

### Role 2 — Customer

**Registration:** Choose "Customer" role → immediate access after registration.

**Workflow:**
```
Register / Login as Customer
│
├── Discover Professionals (Dashboard)
│   ├── Filter by service type
│   ├── Search by name, location, PIN, description
│   └── Sort by: rating (default) | price low→high | price high→low | experience
│
├── Book a Service
│   ├── Select a professional
│   ├── Set proposed price
│   ├── Set requested date
│   └── Submit → email sent to both customer and professional
│
├── Manage Bookings (Service History)
│   ├── View all requests and their statuses
│   ├── Edit proposed price (only while status = REQUESTED)
│   └── Track status: REQUESTED → ACCEPTED → CLOSED → PAID
│
├── Close Service (After Professional Accepts)
│   ├── Submit review (1–5 stars + remarks)
│   └── Status changes to CLOSED
│
└── Make Payment
    ├── View payment summary (dummy payment form)
    └── Confirm → status changes to PAID, confirmation email sent
```

---

### Role 3 — Service Professional

**Registration:** Choose "Service Professional" role → select service type, add description, experience, and document URL → **must wait for admin approval** before accepting jobs.

**Workflow:**
```
Register / Login as Professional
│
├── (Wait for Admin Approval)
│
├── View Incoming Requests (Dashboard)
│   ├── See all REQUESTED bookings directed to you
│   └── Handle each request:
│       ├── Accept → status changes to ACCEPTED, email sent to customer
│       └── Reject → status changes to REJECTED, admin can reassign
│
├── View Job History
│   └── All past requests with statuses and details
│
└── View Summary Stats
    ├── Total accepted jobs
    ├── Total completed (CLOSED/PAID) jobs
    ├── Total rejected jobs
    └── Your average customer rating
```

---

## 🤖 AI Features (Claude Integration)

The app integrates **Anthropic's Claude API** (`claude-haiku-4-5-20251001`) to add three intelligent features, all accessible via a **floating AI chat widget** in the bottom-right corner (available to all logged-in users).

### 1. 💬 AI Chat Assistant
**Endpoint:** `POST /ai/chat`
**Rate limit:** 30 requests/minute

An interactive chat assistant that helps users navigate the platform, understand the booking process, get service recommendations, and answer any platform-related questions.

- Maintains a **10-message conversation history** for contextual responses
- System-prompted to be a helpful household services advisor
- Accessible via the collapsible floating chat widget on every page
- Shows an unread-message badge when new responses arrive

**Example usage:**
```json
Request:  { "message": "How do I book a plumber?", "history": [] }
Response: { "reply": "To book a plumber, go to your dashboard and..." }
```

---

### 2. 💰 AI Price Estimator
**Endpoint:** `POST /ai/estimate-price`
**Rate limit:** 20 requests/minute

Given a service type, base price, and description, Claude suggests a realistic price range calibrated for the Indian market.

**Example usage:**
```json
Request: {
  "service_type": "Plumbing",
  "base_price": 200,
  "description": "Fixing leaking pipes and bathroom fittings"
}

Response: {
  "min_price": 250,
  "max_price": 450,
  "reasoning": "Considering local market rates and the complexity..."
}
```

---

### 3. ✍️ AI Description Generator
**Endpoint:** `POST /ai/generate-description`
**Rate limit:** 10 requests/minute

Helps service professionals write compelling, concise (2–3 sentences, max 80 words) service descriptions based on their service type, years of experience, and skills.

**Example usage:**
```json
Request: {
  "service_type": "Electrician",
  "experience": 5,
  "skills": "wiring, panel installation, safety inspections"
}

Response: {
  "description": "A certified electrician with 5 years of hands-on experience..."
}
```

> **Note:** All AI features return a `503` response if `ANTHROPIC_API_KEY` is not configured. The app continues to function normally without it.

---

## 📡 REST API Documentation

The platform includes a read-only RESTful API for external integrations.

**Base URL:** `http://127.0.0.1:5000/api/v1`

**Authentication:** Include the user's API key in the request header:
```
x-api-key: <your-api-key>
```

---

### Endpoints

#### `GET /services` — Public (no auth required)
Lists all available service categories.

**Rate limit:** 60 per minute

**Response:**
```json
{
  "success": true,
  "count": 3,
  "services": [
    {
      "id": 1,
      "name": "Plumbing",
      "description": "All plumbing services",
      "base_price": 200
    }
  ]
}
```

---

#### `GET /me` — Auth required
Returns the authenticated user's profile information.

**Rate limit:** 30 per minute

**Response:**
```json
{
  "success": true,
  "user": {
    "id": 4,
    "username": "john_customer",
    "email": "john@example.com",
    "role": "customer",
    "address": "123 Main Street",
    "pin": "560001",
    "created_at": "2025-01-08T10:30:00+00:00"
  }
}
```

---

#### `GET /my-requests` — Auth required
Returns the authenticated user's service requests with pagination. Response shape differs for customers vs. professionals.

**Query Parameters:**
| Parameter | Default | Max | Description |
|---|---|---|---|
| `page` | 1 | — | Page number |
| `per_page` | 20 | 100 | Items per page |

**Rate limit:** 30 per minute

**Response:**
```json
{
  "success": true,
  "total": 12,
  "page": 1,
  "pages": 1,
  "requests": [
    {
      "id": 7,
      "service": "Plumbing",
      "status": "accepted",
      "proposed_price": 350,
      "date_requested": "2025-01-08T10:00:00+00:00",
      "date_completed": null,
      "customer": "john_customer",
      "professional": "jane_plumber"
    }
  ]
}
```

---

### API Error Responses
| Code | Meaning |
|---|---|
| `401` | Missing or invalid `x-api-key` |
| `429` | Rate limit exceeded |
| `500` | Server error |

---

## 📧 Email Notification System

The app uses **Flask-Mail** with Gmail SMTP to send **5 types of automated email notifications**. All emails are sent **asynchronously in background threads** so they never slow down the user experience.

| Trigger | Recipient | Subject |
|---|---|---|
| Customer books a service | Customer | Booking Request Sent |
| Customer books a service | Professional | New Service Request |
| Professional accepts a request | Customer | Your Request Was Accepted |
| Professional rejects a request | Customer | Your Request Was Rejected |
| Customer completes payment | Customer | Payment Confirmation |

All emails are sent as **dual-format** (plain text + HTML) for maximum email client compatibility.

> **Note:** Email is optional. The app works fully without mail configured — it silently skips email sending if `MAIL_USERNAME` is not set in `.env`.

---

## 🔒 Security Implementation

| Security Feature | Implementation |
|---|---|
| Password hashing | Werkzeug `generate_password_hash` / `check_password_hash` |
| CSRF protection | Flask-WTF on every form |
| Rate limiting | Flask-Limiter (200/day, 50/hour globally; stricter per route) |
| Session management | Flask-Login with `login_required` decorator |
| Role enforcement | Custom decorators: `@admin_required`, `@customer_required`, `@professional_required` |
| API authentication | `x-api-key` header validated against hashed keys in DB |
| User blocking | Admin can revoke access without deleting the account |
| Professional gating | Must pass admin verification before accepting jobs |
| Database integrity | FK constraints, unique constraints, `CHECK` constraint on rating |
| Input validation | Server-side WTForms with custom uniqueness validators |

---

## 🚀 Getting Started

### Prerequisites
- Python **3.8 or higher**
- `pip` (Python package manager)
- Git

---

### Step 1 — Clone the Repository
```bash
git clone https://github.com/21f2000210/MAD1PROJECT.git
cd MAD1PROJECT
```

---

### Step 2 — Create a Virtual Environment

**Windows (PowerShell / cmd):**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the project root:

```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

Then open `.env` and fill in the values:

```env
# ─── Flask ────────────────────────────────────────────────
SECRET_KEY=your_super_secret_key_here
# Generate one with: python -c "import secrets; print(secrets.token_hex(32))"

# ─── Database ─────────────────────────────────────────────
DATABASE_URI=sqlite:///database.db
# For PostgreSQL: postgresql://user:password@localhost/dbname

# ─── Email (Gmail SMTP) ───────────────────────────────────
# Leave blank to disable email notifications entirely
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_gmail_app_password
# ^ Use a Gmail App Password (not your real password)
# Create one at: https://myaccount.google.com/apppasswords
MAIL_DEFAULT_SENDER=noreply@azhousehold.com

# ─── AI (Anthropic Claude) ────────────────────────────────
# Leave blank to disable AI features
ANTHROPIC_API_KEY=sk-ant-...
# Get your key at: https://console.anthropic.com/
```

> **Gmail App Password:** Go to `Google Account → Security → 2-Step Verification → App passwords`. Select "Mail" and generate a 16-character password. Use that as `MAIL_PASSWORD`.

---

## 🗃 Database Setup & Migrations

Run the following commands once after cloning:

```bash
# Apply all migrations to create the database schema
flask db upgrade
```

> If you ever change `models.py`, run:
> ```bash
> flask db migrate -m "describe your change"
> flask db upgrade
> ```

---

### Generate API Keys for Users

After creating users, generate API keys so they can use the REST API:

```bash
flask generate-keys
```

This prints each user's generated key to the terminal. Copy a key and use it in the `x-api-key` header.

---

## ▶️ Running the Application

```bash
flask run
```

The app will start at: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

For production-like logging, set `FLASK_DEBUG=0` in your environment (logs go to `logs/azhousehold.log`).

---

## 👤 Creating Test Users

The platform has three roles. Here is how to create one of each:

### 1. Create an Admin

The admin role is not available via the registration form (by design — this is a security measure). To create the first admin:

1. Open `app/routes/auth.py`
2. In the `register()` function, find the user creation block
3. Temporarily hardcode `role="admin"` for the new user
4. Register via the web form
5. **Immediately revert the change** after registration

### 2. Create a Service Professional

1. Go to `/register`
2. Select **"Service Professional"** as role
3. Choose a service type from the dropdown
4. Fill in description, years of experience, and a document URL (can be any URL for testing)
5. Register → you will be redirected to a pending approval screen
6. **Log in as Admin** → go to the dashboard → approve the professional
7. The professional can now log in and accept jobs

### 3. Create a Customer

1. Go to `/register`
2. Select **"Customer"** as role
3. Fill in username, email, password, address, and PIN
4. Register → immediate access to the customer dashboard

---

## 🌐 Using the REST API

### Step 1 — Generate your API key
```bash
flask generate-keys
```

Note the key printed for your user.

### Step 2 — Make API calls

**PowerShell (Windows):**
```powershell
# List all services (public)
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/v1/services" | Select-Object -ExpandProperty Content

# Get your profile
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/v1/me" -Headers @{"x-api-key"="YOUR_API_KEY"} | Select-Object -ExpandProperty Content

# Get your requests (page 1, 5 per page)
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/v1/my-requests?page=1&per_page=5" -Headers @{"x-api-key"="YOUR_API_KEY"} | Select-Object -ExpandProperty Content
```

**curl (macOS/Linux/Git Bash):**
```bash
# List all services
curl http://127.0.0.1:5000/api/v1/services

# Get your profile
curl -H "x-api-key: YOUR_API_KEY" http://127.0.0.1:5000/api/v1/me

# Get your requests
curl -H "x-api-key: YOUR_API_KEY" "http://127.0.0.1:5000/api/v1/my-requests?page=1&per_page=5"
```

---

## 🗺 All Routes Reference

### Auth Routes
| Method | URL | Description | Rate Limit |
|---|---|---|---|
| `GET` | `/` | Index — redirects to login | — |
| `GET/POST` | `/login` | User login | 10/min, 50/hr |
| `GET` | `/logout` | Logout current user | — |
| `GET/POST` | `/register` | New user registration | 5/min, 20/hr |

### Admin Routes (`/admin`)
| Method | URL | Description |
|---|---|---|
| `GET` | `/admin/dashboard` | Main admin panel |
| `GET` | `/admin/search` | Search users |
| `POST` | `/admin/services/create` | Create a new service |
| `POST` | `/admin/services/<id>/update` | Update service details |
| `POST` | `/admin/services/<id>/delete` | Delete a service |
| `POST` | `/admin/professionals/<id>/approve` | Approve a professional |
| `POST` | `/admin/professionals/<id>/reject` | Reject a professional |
| `POST` | `/admin/users/<id>/toggle_block` | Toggle block/unblock user |
| `POST` | `/admin/users/<id>/block` | Block a user |
| `POST` | `/admin/users/<id>/unblock` | Unblock a user |
| `POST` | `/admin/request/<id>/reassign` | Reassign rejected request |
| `GET` | `/admin/charts/data` | Chart data (JSON) |
| `GET` | `/admin/export/requests` | Export requests CSV |
| `GET` | `/admin/export/users` | Export users CSV |

### Customer Routes (`/customer`)
| Method | URL | Description |
|---|---|---|
| `GET` | `/customer/dashboard` | Browse & search professionals |
| `POST` | `/customer/book_service/<id>` | Book a professional |
| `POST` | `/customer/request/<id>/update` | Update request price |
| `GET` | `/customer/service_history` | View all bookings |
| `POST` | `/customer/review_service/<id>` | Submit review |
| `GET` | `/customer/payment/<id>` | View payment page |
| `POST` | `/customer/payment/<id>/process` | Process payment |
| `GET` | `/customer/profile/<id>` | View customer profile |

### Professional Routes (`/professional`)
| Method | URL | Description |
|---|---|---|
| `GET` | `/professional/dashboard` | View incoming & past requests |
| `POST` | `/professional/request/<id>/handle` | Accept or reject a request |
| `GET` | `/professional/summary` | View personal statistics |

### Shared Routes (`/shared`)
| Method | URL | Description |
|---|---|---|
| `GET` | `/shared/professional/<id>` | Public professional profile |
| `GET/POST` | `/shared/profile/edit` | Edit own profile |

### REST API Routes (`/api/v1`)
| Method | URL | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/services` | None | List all services |
| `GET` | `/api/v1/me` | API Key | Get own profile |
| `GET` | `/api/v1/my-requests` | API Key | Get own requests (paginated) |

### AI Routes (`/ai`)
| Method | URL | Auth | Rate Limit | Description |
|---|---|---|---|---|
| `POST` | `/ai/chat` | Login | 30/min | Chat assistant |
| `POST` | `/ai/estimate-price` | Login | 20/min | Price estimator |
| `POST` | `/ai/generate-description` | Login | 10/min | Description generator |

---

## 🌙 Dark Mode & UI Features

### Dark Mode
- Toggle button in the navbar (🌙/☀️ icon)
- Preference is saved to **localStorage** — persists across sessions and page refreshes
- Implemented via CSS custom properties and `[data-theme="dark"]` attribute on `<html>`
- Covers all components: cards, tables, forms, modals, buttons, inputs

### Toast Notification System
- Flask flash messages are automatically converted to **animated toast notifications**
- Appear fixed in the **top-right corner**
- Auto-dismiss after **4 seconds**
- 4 styles: `success` (green), `danger` (red), `warning` (yellow), `info` (blue)

### AI Chat Widget
- **Fixed floating button** in the bottom-right corner, visible on every page (when logged in)
- Collapsible panel with a conversation interface
- Shows **unread badge** when AI responds
- Includes a "Clear chat" button
- Typing indicator while waiting for AI response
- Sends conversation history for contextual multi-turn replies

### Password Strength Meter
- Visible on the registration form
- 3-level indicator: Weak / Medium / Strong
- Updates live as the user types

### Charts (Admin Dashboard)
- **Service Request Status Chart**: Visualises the count of requests in each status (Requested, Accepted, Rejected, Closed, Paid)
- **Rating Distribution Chart**: Bar chart of how many reviews have each star rating (1–5)
- Data fetched from `/admin/charts/data` as JSON — charts update without page reload

---

## 📊 Service Lifecycle State Machine

```
            ┌─────────┐
            │ CUSTOMER │
            │  Books   │
            └────┬─────┘
                 │ status = REQUESTED
                 ▼
       ┌─────────────────┐
       │  PROFESSIONAL   │
       │ Reviews Request  │
       └────┬────────┬───┘
            │        │
      Accept│        │Reject
            │        │
            ▼        ▼
       ACCEPTED    REJECTED ──► Admin Reassigns ──► REQUESTED
            │
            │ Customer reviews & closes
            ▼
         CLOSED
            │
            │ Customer pays
            ▼
          PAID ✅
```

---

## 🔧 Useful Commands

```bash
# Run the application
flask run

# Apply database migrations
flask db upgrade

# Create a new migration after model changes
flask db migrate -m "description of change"

# Generate API keys for all users
flask generate-keys

# Run with a specific port
flask run --port 8000

# Run in production mode (disables debug, enables logging)
FLASK_DEBUG=0 flask run
```

---

## 📦 Dependencies Overview

```
alembic==1.16.5          # Database migration engine (used by Flask-Migrate)
anthropic>=0.40.0        # Anthropic Claude AI SDK
blinker==1.9.0           # Signal support for Flask
click==8.2.1             # CLI framework (used by Flask)
colorama==0.4.6          # Terminal color output (Windows)
dnspython==2.8.0         # DNS resolution (used by email-validator)
email-validator==2.3.0   # Email format validation in WTForms
Flask==3.1.2             # Core web framework
Flask-Limiter==3.9.0     # Request rate limiting
Flask-Login==0.6.3       # User session management
Flask-Mail==0.10.0       # Email sending via SMTP
Flask-Migrate==4.1.0     # SQLAlchemy database migrations
Flask-SQLAlchemy==3.1.1  # SQLAlchemy ORM integration
Flask-WTF==1.2.2         # WTForms integration + CSRF
greenlet==3.2.4          # Async support for SQLAlchemy
idna==3.10               # Internationalized domain names
itsdangerous==2.2.0      # Secure data signing (Flask sessions)
Jinja2==3.1.6            # HTML templating engine
Mako==1.3.10             # Template engine (used by Alembic)
MarkupSafe==3.0.2        # Safe HTML string handling
python-dotenv==1.1.1     # Load .env files into environment
SQLAlchemy==2.0.43       # ORM and database toolkit
typing_extensions==4.15.0 # Type hint backports
Werkzeug==3.1.3          # WSGI utilities, password hashing
WTForms==3.2.1           # Form validation library
```

---

*Built with ❤️ using Flask, SQLAlchemy, Bootstrap 5, and Claude AI.*
