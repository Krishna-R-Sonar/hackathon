# Order Service Benchmark Project

An e-commerce order and inventory processing microservice used as the controlled evaluation benchmark for testing `graph-agent-memory`.

## Features
- Order creation and status tracking (`models.py`)
- In-memory stock reservations and rollback handling (`storage.py`)
- Business workflows and state transitions with audit logging (`service.py`)
- Comprehensive error domain hierarchy (`errors.py`)

## Running Tests
```powershell
pytest -v
```
