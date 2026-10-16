#!/usr/bin/env python3
"""
FalkorDB Health Check Script.
Verifies container connectivity, responsiveness, and graph readiness.
"""

import sys
import json
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from graph_memory.db import get_db


def main():
    print("Checking FalkorDB connection...")
    db = get_db()
    health = db.check_health()
    print(json.dumps(health, indent=2))
    
    if health.get("status") == "healthy":
        print("[SUCCESS] FalkorDB is running and healthy!")
        sys.exit(0)
    else:
        print("[ERROR] FalkorDB health check failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
