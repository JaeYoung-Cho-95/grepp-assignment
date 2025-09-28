set -euo pipefail
docker compose exec server bash -lc "coverage run --source='.' manage.py test && coverage html"
open htmlcov/index.html