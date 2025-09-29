set -euo pipefail

docker compose up -d

docker compose exec server bash -lc "python manage.py migrate --noinput"

docker compose exec server bash -lc "python scripts/seed_dummy_data.py"

echo "Seed data generation completed."