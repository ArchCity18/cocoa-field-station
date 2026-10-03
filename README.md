# Cocoa Plot Decision Support

A demo prototype for human-reviewed cocoa black-pod decisions. Every observation is simulated. This is not farm advice, and the configured agronomy values are placeholders that require verification with a qualified cocoa extension source.

The app opens on an interactive welcome screen with a **Get started** button, followed by Google sign-in or account creation through Google OpenID Connect. The app never collects or stores passwords. The field overview has selectable plot cards, weather measure and date-window controls, a human review form, and a filterable decision journal. A cocoa-inspired Streamlit theme is in `.streamlit/config.toml`.

## Setup

Requires Python 3.11 or newer.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:LLM_MOCK = "1"
streamlit run app.py
```

## Configure sign-in

Sign-in requires a Google OAuth client. Create a Google OAuth web client with `http://localhost:8501/oauth2callback` as an authorized redirect URI. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then replace the client ID, client secret, and cookie secret. Keep `secrets.toml` private; it is excluded by `.gitignore`. For a deployed app, set the redirect URI to the public app URL ending in `/oauth2callback` and register the same URI with Google.

The **Create account** option sends users to Google's sign-in flow, where they can create a Google account if needed. This prototype does not create a separate Cocoa account. It stores plot and decision data in one shared local SQLite database, so sign-in does not yet provide per-user data isolation.

The app creates `cocoa.db` on first run and seeds 30 days of simulated weather for three plots. Set `COCOA_DB_PATH` to change the database location. Use `pytest` to run the unit tests.

## AMD hosted model endpoint

Set `LLM_MOCK=0`, `LLM_BASE_URL` to the OpenAI-compatible API base URL, `LLM_API_KEY` to the endpoint key if required, and `LLM_MODEL` to the served model name. The client calls `/chat/completions`. Endpoint and model settings depend on the selected AMD service; confirm their values with its documentation. No live endpoint was configured or verified for this prototype.

## Two-minute demo

1. Open Plot A and get a recommendation; review its weather evidence and confidence, then approve it.
2. Open Plot B; its missing observations reduce confidence and trigger the inspection gate. Record an inspection override with a reason.
3. Open Plot C, generate a recommendation, and review any cited override cases.
4. Show the Audit Log and the human decision/reason fields. To demonstrate more cautious feedback clearly, record two cautious overrides in the same risk bucket first.

All rule thresholds in `config.yaml` are marked as placeholders. Do not present them as validated agronomy guidance. The LLM runs in mock mode unless an endpoint is configured.
