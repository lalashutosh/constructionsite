PY=.venv/bin/python

setup:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements.txt

check:
	$(PY) scripts/check_env.py

test:
	$(PY) -m pytest -q

eval-stub:
	$(PY) -m evalkit.run --engine stub --split all

eval:
	$(PY) -m evalkit.run --engine pipeline --split dev

eval-holdout:
	$(PY) -m evalkit.run --engine pipeline --split holdout

api:
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

demo:
	@echo "terminal 1: make api   |  terminal 2: make web   |  open http://localhost:5173"

eval-nosib:
	$(PY) -m evalkit.run --engine pipeline --split dev --no-siblings

recon:
	$(PY) scripts/recon.py

claims:
	@test -d web && mkdir -p web/public && cp evalkit/out/latest/claims.json web/public/claims.json || true

web-build:
	cd web && npm run build

readme:
	$(PY) scripts/gen_readme.py

.PHONY: readme setup check test eval-stub eval eval-holdout eval-nosib api web demo recon claims web-build
