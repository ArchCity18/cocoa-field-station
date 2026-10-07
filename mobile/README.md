# Cocoa Field Station — Expo security assignment

This Expo React Native application and PHP/MySQL API demonstrate user identification, two-factor authentication, four role permissions, salted and peppered password hashing, a local XAMPP server, and an offline-capable local database. The Streamlit application has a separate Google OIDC/TOTP sign-in and SQLite database; neither app shares accounts or data with the other.

## Requirement checklist

| Requirement | Streamlit web app | Expo mobile/web app |
| --- | --- | --- |
| Identify a user | Verified Google subject and email | Normalized email/password or verified Google subject |
| Two-factor authentication | TOTP authenticator code after Google sign-in | TOTP after password or Google sign-in |
| Role authorization | Inputer, manager, admin, administrator | API-enforced inputer, manager, admin, administrator |
| Password storage | Google handles the Google password; app stores none | PHP Argon2id hash, automatic unique salt, private server pepper |
| Frontend | Streamlit | Expo / React Native |
| Database | Local SQLite | Local MySQL via XAMPP |
| Secure DB access | SQLite local file; hosted app has separate storage | PDO prepared statements and a restricted MySQL account |
| Local server | `streamlit run app.py` | Apache/PHP + MySQL in XAMPP |
| Access balance | Shared field workspace; role-gated entry and account actions | Shared plots; role-gated entry and account actions |

## Role permissions

| Role | Enter plot observations | Add inputers | Remove inputers |
| --- | --- | --- | --- |
| Inputer | Yes | No | No |
| Manager | Yes | Yes | No |
| Admin | No | No | Yes |
| Administrator | Yes | Yes | Yes |

Removing an Expo inputer deactivates the account and revokes its API sessions. This preserves field history and its audit trail. Streamlit records are attributed by the signed-in Google email; removing an inputer blocks that Google identity until a manager invites the email again. The manager's “Add inputer” action creates an invitation. The invited person activates it by registering/signing in with that email; the app does not send invitation email.

## Start the local server and database

1. Copy the contents of `backend/` to `C:\xampp\htdocs\cocoa-security\` so `api.php` is at `C:\xampp\htdocs\cocoa-security\api.php`.
2. Start Apache and MySQL from XAMPP Control Panel.
3. Open `http://localhost/phpmyadmin`. For a new install, import `backend/schema.sql`. For a database created by an earlier version, back it up, then import `backend/migrations/002_google_totp.sql` if not already applied, followed by `backend/migrations/003_roles_inputers_and_audit.sql` exactly once.
4. Create a restricted MySQL login from phpMyAdmin's SQL page (choose a strong unique password):

   ```sql
   CREATE USER 'cocoa_app'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_A_LONG_RANDOM_DATABASE_PASSWORD';
   GRANT SELECT, INSERT, UPDATE, DELETE ON cocoa_security.* TO 'cocoa_app'@'127.0.0.1';
   ```

5. Copy `backend/config.example.php` to `C:\xampp\htdocs\cocoa-security\backend\config.php`. Set its database password to the same value, generate a long random `pepper`, and keep the file private. It must never be committed.
6. Make sure `allowed_origins` includes the exact Expo web origin you use (normally `http://localhost:8081` or `http://127.0.0.1:8081`). Native requests do not send a browser origin. Keep the API on localhost or a trusted private network.
7. Visit `http://localhost/cocoa-security/api.php?route=health`. The response should be JSON with `ok: true`.

The API uses PDO with emulated prepares disabled. It performs no schema changes at runtime, so the app database login does not need CREATE, ALTER, or DROP privileges. The local database is not encrypted at rest; protect the computer account and back up the database securely.

## Run the Expo client

```powershell
cd C:\Users\Archilles\Documents\Hackathon\mobile
npm install
npm start
```

Run `npm run web` for the browser client. The API URL in `src/api.js` is configured for the local browser and Android emulator. For a physical phone, use the computer's LAN IP in that file and allow Apache through Windows Firewall on a private network. Keep the phone and computer on the same trusted Wi-Fi.

## Google sign-in and TOTP

For Expo web, create a Google OAuth web client and register the exact redirect URI shown by the app; configure its web client ID in the private XAMPP `config.php`. No Google client secret belongs in the Expo bundle. The PHP API verifies Google's signed ID token and verified email. Native Android/iOS OAuth requires platform OAuth clients and an Expo development build; Expo Go does not provide the native OAuth callback setup.

Email/password registration identifies users by normalized email. The first successful login starts TOTP enrollment: scan the QR/manual key using Google Authenticator or another compatible authenticator, then enter a six-digit code. Subsequent logins require a current code. Challenges expire after ten minutes and allow five failed attempts. TOTP secrets are encrypted before storage, and session tokens are stored as SHA-256 digests and expire after twelve hours.

## Assign elevated roles

Public registration always creates an inputer; it cannot submit a privileged role. After the intended account registers, promote it locally in phpMyAdmin. Choose exactly one appropriate role:

```sql
UPDATE users SET role='manager' WHERE email='manager@example.com';
UPDATE users SET role='admin' WHERE email='admin@example.com';
UPDATE users SET role='administrator' WHERE email='owner@example.com';
```

Reload the app or sign in again. The API checks roles on protected routes and returns HTTP 403 for an unauthorized action; client-side navigation is only a convenience.

For Streamlit, set `MANAGER_EMAILS`, `ADMIN_EMAILS`, and/or `ADMINISTRATOR_EMAILS` in local `secrets.toml` or Community Cloud Secrets, for example `ADMIN_EMAILS = ["admin@example.com"]`. Streamlit authentication uses Google OIDC and TOTP, not locally stored passwords.

## Security and limitations

PHP's `password_hash(..., PASSWORD_ARGON2ID)` creates a unique random salt and stores its algorithm/cost metadata with each hash; the private server pepper is added before hashing. Passwords and TOTP codes are not stored. Parameterized SQL prevents user input from being interpolated into database statements. Role checks are enforced server-side. Database transport is local TCP for XAMPP; public use requires TLS, restrictive origin configuration, rate limiting, secure backups, secret rotation, and an account recovery plan.

The Streamlit Community Cloud app does not connect to this local MySQL database. Its SQLite file is separate and is not configured as durable shared production storage. Both apps use shared plot data within their own database. Weather rows are example/simulated data, and recommendations are illustrative rather than validated farm advice.
