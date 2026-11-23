.PHONY: install dev-backend dev-frontend test test-backend test-frontend lint typecheck build package-skill clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -e ".[dev]"
	cd frontend && npm install

dev-backend:
	$(PYTHON) -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test-backend:
	$(PYTHON) -m pytest backend/tests tests -v

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

lint:
	ruff check backend cli skills tests
	cd frontend && npm run lint

typecheck:
	$(PYTHON) -m mypy backend cli
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

package-skill:
	$(PYTHON) -c "import zipfile, pathlib; root = pathlib.Path('skills/api-detective'); out = pathlib.Path('API-Detective-Agensi-Skill.zip'); zf = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED); [zf.write(p, p.relative_to(root).as_posix()) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc')]; zf.close()"

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache frontend/dist
