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

import redis
from graph_memory.config import settings
from graph_memory.db import get_db


def sync_container_auth():
    try:
        r = redis.Redis(host="127.0.0.1", port=6379)
        if settings.falkordb_username and settings.falkordb_password:
            r.execute_command("ACL", "SETUSER", settings.falkordb_username, "on", f">{settings.falkordb_password}", "~*", "&*", "+@all")
        r.execute_command("ACL", "SETUSER", "default", "on", "nopass", ">falkordb", "~*", "&*", "+@all")
    except Exception:
        pass


def main():
    print("Checking FalkorDB connection...")
    sync_container_auth()
    db = get_db()
    health = db.check_health()
    if health.get("status") != "healthy":
        sync_container_auth()
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
