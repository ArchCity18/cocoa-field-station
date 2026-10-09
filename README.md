# Cocoa Plot Decision Support

A demo prototype for human-reviewed cocoa black-pod decisions. Every observation is simulated. This is not farm advice, and the configured agronomy values are placeholders that require verification with a qualified cocoa extension source.

The app opens on an interactive welcome screen with a **Get started** button, followed by Google sign-in or account creation through Google OpenID Connect. The app never collects or stores passwords. The field overview has a plot selector, weather measure and date-window controls, a human review form, and a filterable decision journal. A cocoa-inspired Streamlit theme is in `.streamlit/config.toml`.

The app includes a deterministic mock recommender so the demo works without an AI service. Streamlit Community Cloud hosts the app code; it does not bundle or run a separate model automatically. To use a live model, connect an OpenAI-compatible chat-completions endpoint and provide its model name and, if required, API key.

## Information Security mobile assignment

The Streamlit app uses Google OpenID Connect for identity and Google Authenticator TOTP as a second factor. The Expo assignment in [`mobile/`](mobile/) uses a React Native client and PHP API in [`backend/`](backend/); it supports email/password or Google identity, TOTP, Argon2id password hashes with per-password salts and a private pepper, and four server-checked roles. Local development still works with SQLite and XAMPP MySQL. For the shared cloud setup, both server backends use Supabase PostgreSQL: plot observations and decisions are shared, while the two apps retain their separate sign-in records. See [`backend/supabase_schema.sql`](backend/supabase_schema.sql), [`mobile/README.md`](mobile/README.md), and the two-page paper in [`docs/Secure_Login_System_Implementation_Report.docx`](docs/Secure_Login_System_Implementation_Report.docx).

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

Sign-in requires a Google OAuth client. Create a Google OAuth web client with `http://localhost:8501/oauth2callback` as an authorized redirect URI. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then replace the client ID, client secret, and cookie secret. Keep `secrets.toml` private; it is excluded by `.gitignore`. For a deployed app, set the redirect URI to the public app URL ending in `/oauth2callback` and register the same URI with Google. After Google sign-in, users enroll in Google Authenticator; future Streamlit sessions require a six-digit TOTP code. Keep the `[auth].cookie_secret` stable because it also encrypts authenticator secrets stored in the app database. Inputer is the default role. Use optional Streamlit Secrets lists `MANAGER_EMAILS = ["manager@example.com"]`, `ADMIN_EMAILS = ["admin@example.com"]`, and `ADMINISTRATOR_EMAILS = ["owner@example.com"]` to bootstrap elevated accounts. The administrator list takes precedence. A configured elevated email is promoted on sign-in; ordinary new accounts get the inputer role.

The role rules are the same in both clients: an inputer can enter observations; a manager can add inputers; an admin can deactivate inputers; an administrator can do both. Roles are checked by the backend/API or Streamlit account layer, not only by hiding buttons. Streamlit role allowlists are read from Community Cloud Secrets as well as local `secrets.toml`.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub. Keep `.streamlit/secrets.toml` private; only commit the `.streamlit/secrets.toml.example` template.
2. At [share.streamlit.io](https://share.streamlit.io), choose **Create app**, select `ArchCity18/cocoa-field-station`, branch `main`, and entrypoint `app.py`.
3. Deploy once to reserve the app URL. Open the app's **Settings → Secrets** and paste a TOML configuration based on `.streamlit/secrets.toml.example`. Set `[auth].redirect_uri` to `https://YOUR-APP-NAME.streamlit.app/oauth2callback`. Reuse your OAuth client ID, but use a newly rotated Google client secret if the old one was ever shared.
4. Add that same HTTPS callback URL to the Google OAuth web client's **Authorized redirect URIs**, save the client, then reboot the Community Cloud app.

For the no-provider demo, keep `LLM_MOCK = "1"`. To use a real provider, add these root-level keys in Community Cloud **Secrets** and set mock mode to `"0"`:

```toml
LLM_MOCK = "0"
LLM_BASE_URL = "https://YOUR-PROVIDER-BASE-URL/v1"
LLM_MODEL = "YOUR-SERVED-MODEL-NAME"
LLM_API_KEY = "YOUR-PROVIDER-API-KEY"
```

The endpoint should support `POST {LLM_BASE_URL}/chat/completions` and return an OpenAI-compatible chat-completions response. Get the URL, model name, and key from your chosen model host; do not commit them to GitHub. The app falls back to its mock recommender if the model URL or model name is missing.

The local SQLite database is suitable for a prototype demo and is not configured as durable shared storage for a hosted production app.

## Shared Supabase database

1. In the Supabase project, open **SQL Editor**, create a new query, paste the contents of [`backend/supabase_schema.sql`](backend/supabase_schema.sql), and run it once. The script creates the app tables, seeds the three plot names, enables row-level security, and denies direct table access to browser/mobile API roles.
2. In **Project → Connect**, choose **Session pooler** and copy the PostgreSQL connection URI. Keep its database password private. The URI is used only by server code; never put it in `mobile/.env` or an Expo build.
3. In local `.streamlit/secrets.toml` and Streamlit Community Cloud **Settings → Secrets**, add `COCOA_DATABASE_URL = "the-private-session-pooler-uri"`.
4. For the PHP API, copy the Supabase host, port, database, username, and password from that connection URI into the private `backend/config.php`. Set `db_driver` to `pgsql`, `db_name` to `postgres`, and keep `db_dsn` empty or set a `pgsql:...;sslmode=require` DSN. The PHP host must have PDO_PGSQL enabled. The example config is a template; do not commit the real config.
5. XAMPP can continue to serve the PHP API for local phone testing, but your computer and Apache must remain on. The Expo app connects to that API; Supabase holds the shared records. To use Expo away from your local network, the PHP API itself must also be deployed to a public HTTPS host.

The SQL schema enables RLS and gives no direct table permissions to `anon` or `authenticated`. The server-side database credentials bypass those client policies and therefore must remain private. Server endpoints continue to authorize roles and use parameterized statements. Configure the cloud URI only after running the schema, then restart/reboot the corresponding app.

The **Create account** option sends users to Google's sign-in flow, where they can create a Google account if needed. This prototype does not create a separate Cocoa account for the Streamlit client. Streamlit and Expo retain separate account tables, while plot observations and decisions can be shared through the Supabase setup above. Shared records are visible to authenticated field-station users; they are not partitioned per user.

The app creates `cocoa.db` on first run and seeds 30 days of simulated weather for three plots. Set `COCOA_DB_PATH` to change the database location. Use `pytest` to run the unit tests.

## AMD hosted model endpoint

Set `LLM_MOCK=0`, `LLM_BASE_URL` to the OpenAI-compatible API base URL, `LLM_API_KEY` to the endpoint key if required, and `LLM_MODEL` to the served model name. The client calls `/chat/completions`. Endpoint and model settings depend on the selected AMD service; confirm their values with its documentation. No live endpoint was configured or verified for this prototype.

## Two-minute demo

1. Open Plot A and get a recommendation; review its weather evidence and confidence, then approve it.
2. Open Plot B; its missing observations reduce confidence and trigger the inspection gate. Record an inspection override with a reason.
3. Open Plot C, generate a recommendation, and review any cited override cases.
4. Show the Audit Log and the human decision/reason fields. To demonstrate more cautious feedback clearly, record two cautious overrides in the same risk bucket first.

All rule thresholds in `config.yaml` are marked as placeholders. Do not present them as validated agronomy guidance. The LLM runs in mock mode unless an endpoint is configured.
