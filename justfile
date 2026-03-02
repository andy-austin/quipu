set dotenv-load

# Run both services (Hands must start before Brain)
dev:
    python -m hands.server & sleep 1 && uvicorn brain.server:app --reload --port 8000

# Run Brain only
brain:
    uvicorn brain.server:app --reload --port 8000

# Run Hands only
hands:
    python -m hands.server

# Lint and format
lint:
    ruff check .
    ruff format --check .

# Auto-fix lint and format
fix:
    ruff check --fix .
    ruff format .

# Type check
typecheck:
    pyright

# Run all tests
test:
    pytest

# Health check
health:
    curl -s http://localhost:8000/health | python -m json.tool

# Deploy Brain to Fly.io
deploy-brain:
    fly deploy -c brain/fly.toml --dockerfile brain/Dockerfile

# Deploy Hands to Fly.io
deploy-hands:
    fly deploy -c hands/fly.toml --dockerfile hands/Dockerfile

# Install dependencies
sync:
    uv sync
