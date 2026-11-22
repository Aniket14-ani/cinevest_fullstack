# CineVest — Full-stack demo

A local educational prototype for a movie-project funding marketplace. It includes:
- React + Vite frontend
- Python FastAPI backend
- SQLite database (easy local development; can be changed to PostgreSQL)
- Demo login/register, movie listings, producer project submission, virtual allocations, portfolio and admin review
- Seeded fictional movies
- No payment gateway and no real-money investment features

## Safety / scope
All data and balances are for demo use only. The application does not offer real securities, ownership, investment returns or payment processing. Do not connect real money or use it to solicit investments. Obtain qualified Indian legal/regulatory advice before any real-money launch.

## Requirements
- Python 3.10+
- Node.js 18+

## 1. Start the backend
Open a terminal in `backend/`:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs

The database `cinevest.db` is created automatically and seeded with fictional demo projects.
For a convenient local demo, the backend exposes a development-only login/register flow. Do not expose this backend publicly without replacing the demo security configuration.

## 2. Start the frontend
Open a second terminal in `frontend/`:

```bash
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173).

## Demo accounts
Seeded admin:
- Email: `admin@cinevest.demo`
- Password: `DemoAdmin123!`

You can register a regular demo account in the UI. Registration starts with ₹100,000 virtual credits.

## Demo workflow
1. Log in as admin and approve/reject producer-submitted projects.
2. Register a regular user to browse projects and allocate virtual credits.
3. Register a producer account or use the producer submission form to submit a project.
4. Review portfolio and transaction history.

## Important implementation notes
- Passwords are hashed with bcrypt.
- Authentication uses JWT for this local demo.
- Virtual credit allocations are recorded in a database transaction.
- This is not production-ready: add rate limiting, email verification, password reset, robust authorization review, audit logging, backups, deployment secrets, migrations, automated tests and professional security review before deployment.
