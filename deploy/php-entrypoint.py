#!/usr/bin/env python3
"""Create PHP API's required config.php from injected runtime secrets."""
import os
import json
from pathlib import Path

config = {
    "db_driver": os.environ.get("COCOA_DB_DRIVER", "pgsql"),
    "db_host": os.environ.get("COCOA_DB_HOST", ""),
    "db_port": int(os.environ.get("COCOA_DB_PORT", "5432")),
    "db_name": os.environ.get("COCOA_DB_NAME", ""),
    "db_user": os.environ.get("COCOA_DB_USER", ""),
    "db_password": os.environ.get("COCOA_DB_PASSWORD", ""),
    "db_dsn": os.environ.get("COCOA_DB_DSN", ""),
    "pepper": os.environ.get("COCOA_PEPPER", ""),
    "allowed_origins": json.loads(os.environ.get("COCOA_ALLOWED_ORIGINS", '["http://localhost:8081"]')),
    "google_web_client_id": os.environ.get("COCOA_GOOGLE_WEB_CLIENT_ID", ""),
    "google_android_client_id": os.environ.get("COCOA_GOOGLE_ANDROID_CLIENT_ID", ""),
    "google_ios_client_id": os.environ.get("COCOA_GOOGLE_IOS_CLIENT_ID", ""),
    "llm_enabled": os.environ.get("COCOA_LLM_ENABLED", "false").lower() == "true",
    "llm_base_url": os.environ.get("COCOA_LLM_BASE_URL", ""),
    "llm_model": os.environ.get("COCOA_LLM_MODEL", ""),
    "llm_api_key": os.environ.get("COCOA_LLM_API_KEY", ""),
}

required = ["db_host", "db_name", "db_user", "db_password", "pepper"]
missing = [k for k in required if not config[k]]
if missing:
    raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

config_path = Path("/var/www/html/cocoa-security/config.php")
config_path.parent.mkdir(parents=True, exist_ok=True)
config_path.write_text("<?php\nreturn " + json.dumps(config, indent=4) + ";\n")
config_path.chmod(0o600)

print("Config written, starting Apache...")
os.execvp("apache2-foreground", ["apache2-foreground"])