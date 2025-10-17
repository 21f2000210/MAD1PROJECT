# A-Z Household Services Platform

**A-Z Household Services** is a full-featured, multi-user web application built with Python and Flask. It serves as a comprehensive platform connecting customers seeking household services with skilled professionals.

---

## Key Features

This project goes beyond basic requirements to include a full suite of features expected of a modern web application:

#### Core Functionality
-    A secure system with three distinct roles: **Admin**, **Customer**, and **Service Professional**. Each role has a dedicated dashboard and tailored permissions.
-   **Complete Service Lifecycle:** Full end-to-end workflow: a customer books a service, the professional accepts/rejects, the customer closes and reviews the service, and finally, completes a dummy payment.
-   **Admin Powerhouse Dashboard:** Admins have full oversight to manage services (CRUD), approve/reject new professionals, and block/unblock any user on the platform.
-   **Rejected Request Management:** A critical business logic feature where admins can reassign service requests that have been rejected by a professional, ensuring customer satisfaction.

#### Advanced Features
-   **RESTful API:** A secure, token-authenticated, read-only API for key resources (`/services`, `/me`, `/my-requests`), demonstrating modern backend design.
-   **Interactive Data Visualization:** The admin dashboard features dynamic charts rendered with **Chart.js**, providing at-a-glance insights into service request statuses and customer ratings.
-   **Robust Validation:** Secure, server-side form validation using **WTForms** for all user inputs, including custom validators for uniqueness checks and CSRF protection on all forms.
-   **Advanced Search:** Dynamic, multi-parameter search functionality for both customers (to find professionals by service, name, or location) and admins (to find and manage users).
-   **Public Profiles:** Professionals have public-facing profiles that display their details and aggregate customer reviews, building trust and transparency on the platform.

---

## Tech Stack

-   **Backend:** Python, Flask
-   **Database:** SQLite with Flask-SQLAlchemy (ORM) and Flask-Migrate (Schema Migrations)
-   **Frontend:** Jinja2 Templates, Bootstrap 5, Chart.js
-   **Forms & Security:** Flask-WTF for secure forms and CSRF protection.
-   **Authentication:** Flask-Login for robust session management and route protection.
-   **API:** Pure Flask implementation with custom token authentication.
-   **Deployment:** Designed for local deployment, runs on any machine with Python.

---

## Getting Started

Follow these instructions to get the project running on your local machine.

### 1. Prerequisites
-   Python 3.8+
-   Git

### 2. Clone the Repository
Open your terminal and clone the repository:
```bash
git clone https://github.com/21f2000210/MAD1PROJECT.git
cd [Your-Repo-Name]
```

### 3. Set Up the Environment
Create and activate a virtual environment to manage dependencies.

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
Install all required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
The application uses a `.env` file for configuration. Create one from the example file:
```bash
# On Windows (cmd.exe)
copy .env.example .env

# On macOS/Linux/Git Bash
cp .env.example .env
```
Now, open the newly created `.env` file. You must generate a secure `SECRET_KEY`. Run this command in your terminal:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```
Copy the output and paste it into your `.env` file:
```
SECRET_KEY='your_super_secret_generated_key_here'
```

### 6. Initialize the Database
Run the Flask-Migrate commands to create the database schema:
```bash
# Set up the Flask CLI environment
# (You may need to do this once per terminal session if you don't use a .flaskenv file)
# On Windows (PowerShell): $env:FLASK_APP = "run.py"
# On macOS/Linux: export FLASK_APP=run.py

# Create the database tables
flask db upgrade
```
*Note: If starting from a completely fresh clone, you may need to run `flask db init` and `flask db migrate` first.*

---

## How to Run the Application

With the environment set up, run the application using the Flask CLI:
```bash
flask run
```
The application will be available at: **http://127.0.0.1:5000**

### Creating Users for Testing

1.  **Admin:** The first user must be an admin. To create one, temporarily uncomment the `# role="admin"` line in the `register()` function in `app/routes/auth.py`. Register the user, then **immediately comment out or delete that line** to close the security loophole.
2.  **Service Professional:** Register a new user with the "Service Professional" role. You must log in as the admin to approve this user from the admin dashboard before they can accept jobs.
3.  **Customer:** Register a new user with the "Customer" role.

### Using the API
To use the protected API endpoints, you first need to generate API keys for your users:
```bash
flask generate-keys
```
Copy a generated key and use it in the `x-api-key` header when making a request:
```bash
# Example using curl on Windows (use curl.exe)
curl.exe -H "x-api-key: your_copied_api_key" http://127.0.0.1:5000/api/v1/me
```
