"""Create Streamlit's required secrets file from an injected runtime secret."""
import os
from pathlib import Path

import streamlit

secret_text = os.environ.get("COCOA_STREAMLIT_SECRETS_TOML", "").strip()
if not secret_text:
    raise SystemExit("Missing COCOA_STREAMLIT_SECRETS_TOML runtime secret.")

secrets_dir = Path("/app/.streamlit")
secrets_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
secrets_file = secrets_dir / "secrets.toml"
secrets_file.write_text(secret_text + "\n", encoding="utf-8")
secrets_file.chmod(0o600)
os.execvp("streamlit", ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"])