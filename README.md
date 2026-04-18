# DM4PRICE

DM4PRICE is a Django marketplace focused on trusted price discovery, safer seller interactions, and stronger conversion signals for a competitive market.

## What It Does

- Browse product listings by category, search term, price range, and sort order.
- Highlight boosted listings and verified sellers in discovery flows.
- Let sellers create, edit, and manage listings with product images.
- Support product ratings, seller trust signals, and reporting workflows.
- Track promotion-driven discovery and seller engagement analytics.
- Measure product views, WhatsApp contact clicks, and click-through rate.

## Core Highlights

- Discovery ranking that uses promotion status, ratings, and recency.
- Promotion checkout flow with active promotion windows.
- Trust and safety features for product and seller reporting.
- Seller dashboard analytics for listing performance and ROI visibility.
- Custom user model with seller and verification states.

## Tech Stack

- Python
- Django 5.2
- SQLite for local development
- Pillow for image handling

## Local Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies.
4. Copy `.env.example` to `.env` and update values.
5. Run migrations.
6. Start the development server.

```powershell
git clone https://github.com/Eelblitz/d4p.git
cd d4p
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

## Tests

Run the product test suite with:

```powershell
python manage.py test products
```

Run all tests with:

```powershell
python manage.py test
```

## Branch Workflow

This project uses a simple branch-based workflow for safer updates:

- `main`: production-ready code only.
- `develop`: integration branch for approved work before release.
- `feature/<name>`: new features and upgrades.
- `fix/<name>`: bug fixes.
- `hotfix/<name>`: urgent fixes that must land quickly.

Recommended flow:

1. Branch from `develop`.
2. Make changes in a `feature/*` or `fix/*` branch.
3. Open a pull request into `develop`.
4. Test and review the branch.
5. Merge `develop` into `main` for releases.

More detail is in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Deployment Notes

- Do not commit `.env`, `db.sqlite3`, `media/`, or `venv/`.
- Use PostgreSQL in production by setting `DATABASE_URL`.
- Set `DEBUG=False` and configure secure production settings before deployment.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
