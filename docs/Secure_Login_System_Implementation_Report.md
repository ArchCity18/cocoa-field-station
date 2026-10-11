# Design and Implementation of a Role-Based Two-Factor Authentication System

**Project:** Cocoa Field Station
**Course:** Information Security
**Prepared by:** ______________________________
**Date:** 11 October 2026

## Abstract

This assignment documents the design and implementation of a small field-record system for cocoa plots. The work began as a Streamlit prototype and grew to include an Expo mobile client, a PHP API, role-based permissions, two-factor authentication, shared PostgreSQL storage, and an automated encrypted backup workflow. The system demonstrates security controls in a working application, while also showing where a coursework prototype falls short of a service ready for public use. All crop and weather readings are simulated; the recommendations and risk thresholds are illustrative and must not be used as agronomic advice.

## 1. Project purpose and development journey

The assignment called for a simple login system that could identify users, authenticate them with two factors, authorize actions by role, protect passwords with salt and pepper, connect to an offline database through a local server, and balance security with access. I used the Cocoa Field Station as the application context so the controls would be exercised through realistic tasks: reviewing plot conditions, entering observations, recording decisions, and administering user access.

The first version was a Streamlit web prototype with simulated plot data and a recommendation workflow. Google OpenID Connect was added for identity, followed by Google Authenticator time-based one-time passwords (TOTP). As the requirements became clearer, I added an Expo React Native client and a PHP API hosted locally by Apache in XAMPP. That introduced a separate password-based authentication flow, server-enforced roles, and protected database operations. I then moved the shared plot data to Supabase PostgreSQL so both server applications could use the same field records while keeping their account/session models separate. A live-model option and an encrypted scheduled backup workflow were added around this system.

Development also involved resolving integration issues: redirect URI mismatches in Google OAuth, mismatched app/API configuration, simulated data not appearing in Expo, database driver and connection-string errors, and invalid or oversized model responses. These were addressed by aligning OAuth callbacks with each client, serving field data through the authenticated API, supporting PostgreSQL values correctly, validating model output with a rule-based fallback, and documenting configuration at the server boundary. A later security review reduced the LLM input to weather measurements and decision labels, synchronized Streamlit roles from configured allowlists, and corrected the XAMPP configuration-path instructions.

## 2. System architecture and data flow

The system has two clients and two server-side authentication implementations. Streamlit handles its own Google sign-in and uses the Python data layer. Expo never connects directly to the database; it sends JSON requests to the PHP API. The API verifies credentials or Google's signed ID token, verifies TOTP, issues a bearer token, checks roles, and accesses the database through PDO prepared statements.

```text
Streamlit browser ── Google OIDC ── TOTP ── Streamlit/Python ── SQLite or Supabase PostgreSQL

Expo app ── HTTPS (public) / local HTTP (development) ── PHP API
                                                   ├── Google ID-token validation or password verification
                                                   ├── TOTP challenge ── hashed bearer session
                                                   └── PDO prepared statements ── MySQL or Supabase PostgreSQL

Both server applications can use Supabase for shared plot/weather/decision records.
Their login accounts and MFA enrollment records remain separate.
```

The Streamlit application stores its local prototype database in `cocoa.db`; when configured with `COCOA_DATABASE_URL`, the Python backend uses the shared PostgreSQL database. The PHP API uses the database connection in a private `config.php`, which is not part of the repository. Its connection uses TLS when PostgreSQL is selected. Expo receives only the API address, never the database credentials. The Supabase schema enables row-level security and revokes direct table access from browser/mobile roles; the trusted application servers use private database credentials and apply their own authorization checks.

The principal tables are `users` (Expo accounts and roles), `login_challenges` (short-lived MFA setup/login challenges), `api_tokens` (digests and expiry for Expo sessions), `auth_accounts` (Streamlit Google identities and encrypted TOTP enrollment), `blocked_auth_identities`, `inputer_invites`, `field_plots`, `field_weather`, and `field_decisions`. Database schema changes are applied through checked-in SQL, not dynamically by the API.

## 3. Identification and authentication

### Streamlit

Google OpenID Connect identifies a person by Google's stable subject (`sub`) and verified email. The application does not request or store the user's Google password. On first access the user enrolls an authenticator; later sign-ins require a six-digit TOTP code. Codes are time-based and accepted for a narrow clock-skew window. The app limits failed attempts in the current Streamlit session and requires a new MFA verification after 12 hours. The TOTP secret is encrypted before storage using AES-GCM; the encryption key is derived from the Streamlit `cookie_secret`. This coupling means the cookie secret must remain private and stable unless a deliberate MFA migration or re-enrollment is performed.

### Expo and PHP API

Expo supports verified Google sign-in and an email/password path. The PHP server validates Google's signed ID token, including its signature, issuer, expiry, and configured client audience, and requires Google's verified-email claim. For local passwords, the API normalizes email addresses and uses `password_hash` with Argon2id. PHP generates a unique random salt for every password and stores the encoded hash with algorithm/cost metadata. A separate private server pepper is appended before hashing; `password_verify` performs the password check. Plaintext passwords are not stored. Google-only accounts receive a random unusable local password hash.

After the first factor, the API creates a random MFA challenge that expires after ten minutes. A challenge permits at most five incorrect TOTP submissions. On a successful code, the API consumes the challenge and creates a random 256-bit bearer token valid for twelve hours. It stores only the SHA-256 digest of that token. Authenticated requests send the token in the `Authorization` header; logout removes its digest, and deleting an inputer deactivates the account and revokes that account's tokens. The Expo client uses the platform secure store on iOS and Android; the Expo web client currently uses browser `localStorage`.

Email/password registration is invitation-only while email verification is not configured. This prevents unrestricted public account creation, but an invitation alone does **not** prove that the registrant controls the invited email address. For a public service, registration must add an email verification step or be restricted to verified Google identity. This limitation is retained explicitly rather than describing invitation as proof of identity.

## 4. Authorization and access balance

The applications use role-based access control (RBAC). The API checks the authenticated account's role on each protected operation; hiding a button in Expo is only a usability measure and is not the security control. Streamlit checks account roles before exposing account management or observation entry, and elevated roles are derived from server-side email allowlists. Existing Streamlit accounts are synchronized to those allowlists at login so removing an email from a list removes its elevated role.

| Role | Enter observations | Add inputers | Remove inputers |
|---|:---:|:---:|:---:|
| Inputer | Yes | No | No |
| Manager | Yes | Yes | No |
| Admin | No | No | Yes |
| Administrator | Yes | Yes | Yes |

New accounts receive the least-privileged inputer role. Managers can add inputer invitations; admins can remove inputer accounts but cannot remove managers or administrators. An Expo removal deactivates the user and revokes sessions while preserving field history. Streamlit removal blocks the Google identity until an authorized invitation restores access. These limits divide responsibility and reduce the impact of one compromised ordinary account.

## 5. Database and application security controls

All SQL statements that include user-supplied values use bound parameters: PDO prepared statements in PHP and parameter binding in the Python database layer. PHP disables emulated prepares. Table and column names are application-controlled rather than built from request text. Input validation constrains names, email formats, dates, numeric field readings, allowed actions, and note lengths. The API returns generic authentication errors and does not include database exception details in client responses.

The Supabase schema uses constraints, foreign keys, and indexes to enforce valid roles, actions, metric ranges, and relationships. Row-level security is enabled and direct grants to `anon` and `authenticated` client roles are revoked. This prevents Expo/browser code from bypassing the API and using the public Data API to read application tables. The server credentials remain highly sensitive; a production deployment should use a dedicated least-privilege database role instead of a project-owner or broadly privileged account.

The live LLM is optional. The default demo uses a deterministic mock. When a live model is enabled, Streamlit sends recent weather measurements, calculated risk, and decision labels; free-text field notes, account emails, and override reasons are excluded. The response is parsed and validated against allowed actions and cited decision IDs. If the model is unavailable or returns invalid data, a rule-based suggestion is used. Every recommendation still requires a person to review and record the final decision. Users should still treat weather metrics and plot labels as data disclosed to the configured model provider.

Secrets are kept out of the client bundle and source control. `.gitignore` excludes Streamlit secrets, environment files, private PHP config, database dumps, keys, and backups. OAuth client secrets, the Streamlit cookie secret, database URLs/passwords, the pepper, and model keys belong in private local or hosting secrets. Secrets previously pasted into chat must be rotated. The Streamlit cookie secret is a special case because changing it also makes existing encrypted TOTP enrollments unreadable.

## 6. CIA triad and related information-security principles

### Confidentiality

Confidentiality means information is available only to people and components with a legitimate need. The system supports it through Google OIDC and TOTP, role checks, hashed Expo session tokens, Argon2id password hashes, a server-side pepper, encrypted TOTP secrets, private configuration, TLS for PostgreSQL connections, and denial of direct Supabase client-table access. The LLM payload is minimized to exclude free-text notes and emails. Confidentiality is incomplete for the local XAMPP development setup because its API uses HTTP, and local SQLite/MySQL files are not encrypted at rest by the application. Browser `localStorage` is also accessible to same-origin JavaScript. These modes are suitable only for local/trusted development, not a public production service.

### Integrity

Integrity means records and system behavior remain accurate and are changed only through authorized actions. Parameterized SQL protects query structure from SQL injection. Validation and database constraints reject malformed values. Role checks gate sensitive writes, account removals revoke sessions, and field decisions keep both the recommendation and the human decision/reason. The system deliberately keeps recommendations advisory; a model cannot write a field action on its own. Integrity is supported, but there is no cryptographic audit log or independent tamper-evident record, so a privileged database operator could alter stored history.

### Availability

Availability means authorized users can access the service and records when needed. The mock recommender allows the demo to continue without a model provider, and rule fallback prevents an AI outage from blocking recommendations. Supabase can provide shared hosted storage; local runs can use SQLite/XAMPP. A scheduled GitHub Actions workflow is present to dump schema/data, encrypt the archive, and retain the artifact for 30 days. It only works after repository secrets `SUPABASE_DB_URL` and `BACKUP_ENCRYPTION_KEY` are configured, and a restore has to be tested. The workflow is not proof of successful backup until a scheduled/manual run has completed and its artifact is checked. Availability remains dependent on internet access for Google/Supabase, the host, and unimplemented rate limiting/monitoring.

### Other principles

- **Authentication and authenticity:** Google-verified identities and a second factor provide evidence that a user controls the registered identity and authenticator. Password accounts use a separate factor after password verification. MFA setup keys and recovery remain sensitive and need an operational recovery process.
- **Authorization and least privilege:** Users start as inputers; managers, admins, and administrators receive only the actions assigned to their role. Database clients do not receive direct table privileges. The live server DB account should be further restricted before production.
- **Accountability:** Records include the actor, time, recommendation, human choice, and override reason where available. PHP session tokens are individually revocable. Logs and audit data should be protected and periodically reviewed.
- **Non-repudiation:** The decision journal improves traceability, but it is not strong non-repudiation. There are no digital signatures or tamper-proof audit storage, and a privileged operator could change the database. The report therefore treats this as accountability support, not cryptographic proof.
- **Defense in depth:** Identity provider, TOTP, token expiry, role checks, parameterized SQL, validation, database constraints, secret separation, RLS, and backups protect different parts of the system. A failure in one layer should not automatically grant every capability.
- **Privacy and data minimization:** The model request excludes identifiable emails and field notes. Shared plot data is visible to authenticated field-station accounts and is not partitioned by user, so users should not enter personal or sensitive farm information in this prototype.
- **Secure defaults and usability:** Mock mode works without model credentials; new accounts start with low privilege; challenges and sessions expire; errors are understandable; and the person remains responsible for decisions. Invitation-only signup is a temporary control, not a substitute for email verification.

## 7. Backup, operation, and verification

The workflow at `.github/workflows/supabase-backup.yml` is scheduled daily at 03:23 UTC and can also be run manually. It dumps the linked database schema and data, packages and encrypts the output with OpenSSL, then uploads an encrypted GitHub Actions artifact with a 30-day retention period. The two repository secrets must be present: `SUPABASE_DB_URL` (a database connection URL) and `BACKUP_ENCRYPTION_KEY` (kept separately from the artifact). The backup is not written into Git history. The operational procedure is to inspect workflow success, retain the decryption key outside the repository, periodically download an artifact, restore it into a non-production database, and record the restoration result. An untested archive should not be treated as a proven recovery plan.

The Python unit suite currently has six passing tests, including a regression check that LLM requests do not contain notes or email addresses. Python modules compile successfully, and the PHP API passes PHP syntax lint. These checks verify selected behavior and syntax; they are not penetration testing, a complete Expo device test, or a formal security certification.

## 8. Limitations and next steps

This system is an educational prototype, not a production-ready security service. Before public deployment, the following work is required:

1. Rotate credentials exposed during development and move every replacement to private hosting secrets. Establish a planned rotation process for the pepper and encryption keys.
2. Serve the PHP API only over HTTPS outside localhost. Narrow allowed origins to the actual hosted web origin.
3. Add email ownership verification or require verified Google identity for password-account creation. Add a secure MFA reset and account recovery process.
4. Add shared server-side rate limits for password login, registration, Google login, and TOTP challenges; add monitoring and alerting for repeated failures.
5. Use a dedicated least-privilege database login and verify the permission set for both MySQL and Supabase deployments.
6. Protect browser sessions from script injection and replace long-lived bearer tokens in `localStorage` with a server-managed secure, HttpOnly, SameSite cookie for a production web deployment.
7. Verify automatic backup execution and test restoration. Store encryption/recovery material separately from the backup artifacts.
8. Review data retention, privacy notices, account disablement, audit access, and deployment-specific legal requirements.

## Conclusion

The project demonstrates how identification, two-factor authentication, role-based authorization, password hashing, prepared SQL, encrypted MFA storage, session revocation, data minimization, and backups can work together in a small application. It applies the CIA triad by restricting access, validating and recording changes, and planning recovery. The implementation also makes its remaining gaps visible: local HTTP, unverified email invitations, limited rate limiting and recovery, browser token exposure, and untested backup restoration. That distinction between implemented controls and outstanding work is essential when presenting an information-security system honestly.

## Appendix A. Code excerpts for explaining the implementation

The following short excerpts are taken from the project source. The file and line references point to the current repository revision and may shift if the code changes. In a presentation, introduce the security objective first, point to the excerpt, then explain what it protects and what it does not prove.

### A1. Password hashing with Argon2id and a pepper

**Location:** `backend/api.php`, lines 61–70.

```php
if (strlen($password) < 12 || strlen($password) > 1024) {
    fail(422, 'Use a password between 12 and 1024 characters.');
}
$hash = password_hash($password . $config['pepper'], PASSWORD_ARGON2ID);
$stmt = $pdo->prepare("INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,'inputer')");
$stmt->execute([$name, $email, $hash]);
```

**How to explain it:** “The API rejects passwords outside its allowed length, adds a server-only pepper, and asks PHP to hash with Argon2id. PHP generates a unique salt and stores the algorithm information inside the encoded hash. The database never receives the original password. The pepper is stored outside the client and repository.”

### A2. Verifying the first factor and continuing to TOTP

**Location:** `backend/api.php`, lines 79–85.

```php
$stmt = $pdo->prepare(
    'SELECT id,name,email,password_hash,role,totp_enabled FROM users WHERE email=? AND is_active=1'
);
$stmt->execute([$email]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);
if (!$user || !password_verify($password . $config['pepper'], $user['password_hash'])) {
    fail(401, 'Email or password is incorrect.');
}
start_totp_challenge($pdo, $config, $user);
```

**How to explain it:** “This is the password check. The query only looks up an active account, and the password is checked against the stored Argon2id hash. Correct password alone does not create a session; it starts the second-factor challenge.”

### A3. TOTP challenge limits and one-time session issuance

**Location:** `backend/api.php`, lines 117–142.

```php
if (!$challenge || $challenge['consumed_at'] !== null
    || strtotime($challenge['expires_at'] . ' UTC') < time()
    || (int)$challenge['attempts'] >= 5) {
    $pdo->rollBack();
    fail(401, 'Code expired or attempts exceeded. Sign in again for a new code.');
}
// A valid TOTP is checked before the challenge is consumed.
$token = bin2hex(random_bytes(32));
$tokenHash = hash('sha256', $token);
$pdo->prepare('INSERT INTO api_tokens (user_id,token_hash,expires_at) VALUES (?,?,?)')
    ->execute([$challenge['uid'], $tokenHash, gmdate('Y-m-d H:i:s', time() + 43200)]);
```

**How to explain it:** “A challenge is time-limited, single-use, and capped at five incorrect codes. After successful verification, the server creates a random token and stores only its SHA-256 digest with a 12-hour expiry. If a database leak exposed the token table, the raw bearer tokens would not be present.”

### A4. Parameterized SQL and authenticated role checks

**Location:** `backend/api.php`, lines 426–435.

```php
$stmt = $pdo->prepare(
    'SELECT u.id,u.name,u.email,u.role FROM api_tokens t JOIN users u ON u.id=t.user_id
     WHERE t.token_hash=? AND t.expires_at>? AND u.is_active=1'
);
$stmt->execute([hash('sha256', $token), gmdate('Y-m-d H:i:s')]);
...
function require_role(array $user, array $roles): void {
    if (!in_array($user['role'] ?? '', $roles, true)) {
        fail(403, 'Your role is not allowed to perform this action.');
    }
}
```

**How to explain it:** “The API checks the token digest, expiry, and whether the user is still active. Protected routes then check role on the server. Placeholders bind values separately from SQL syntax, reducing SQL injection risk. Client-side button visibility is not relied on for authorization.”

### A5. Encrypting authenticator secrets in Streamlit

**Location:** `totp.py`, lines 48–57; `app.py`, lines 267–275.

```python
def encrypt_secret(secret, cookie_secret):
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_encryption_key(cookie_secret)).encrypt(
        nonce, secret.encode("ascii"), None
    )
    return base64.b64encode(nonce + ciphertext).decode("ascii")
```

```python
if totp.verify_code(secret, code):
    if not enrolled:
        db.set_totp_secret(sub, totp.encrypt_secret(secret, cookie_secret))
    st.session_state.mfa_verified_sub = sub
    st.session_state.mfa_verified_at = time.time()
```

**How to explain it:** “The authenticator seed must be recoverable by the server to validate future codes, so it cannot be stored as a one-way password hash. Instead, AES-GCM encrypts it with a fresh random nonce. The app stores the encrypted value, not the readable seed. The encryption key depends on the Streamlit cookie secret, so that secret must be protected and kept stable.”

### A6. Minimizing information sent to the live model

**Location:** `agent.py`, lines 18–34.

```python
model_weather = [
    None if row is None else {
        key: row[key]
        for key in ("date", "rainfall_mm", "humidity_pct", "temp_c", "days_since_last_spray")
    }
    for row in last_seven
]
model_cases = [
    {key: case[key] for key in ("id", "plot_id", "risk_bucket", "recommendation", "human_decision")}
    for case in cases
]
```

**How to explain it:** “The database contains additional fields such as free-text inspection notes, account email, and override reasons. This code constructs a smaller allowlisted payload for the model. That is data minimization: only measurements and decision labels needed for the suggestion leave the app.”

### A7. Denying direct client access to Supabase tables

**Location:** `backend/supabase_schema.sql`, lines 118–131.

```sql
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.field_weather ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.field_decisions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.users, public.login_challenges, public.api_tokens,
    public.auth_accounts, public.blocked_auth_identities, public.inputer_invites,
    public.field_plots, public.field_weather, public.field_decisions
    FROM anon, authenticated;
```

**How to explain it:** “The mobile and browser clients do not receive the database password or direct table permissions. They call the application server, which authenticates the request and applies role rules. Row-level security and revoked grants add a database layer against accidental direct access. The server-side database credential still needs least-privilege configuration.”

### A8. Encrypted scheduled database backups

**Location:** `.github/workflows/supabase-backup.yml`, lines 3–6 and 40–62.

```yaml
on:
  schedule:
    - cron: "23 3 * * *"
  workflow_dispatch:
```

```yaml
openssl enc -aes-256-cbc -pbkdf2 -salt \
  -in "/tmp/cocoa-field-station-${stamp}.tar.gz" \
  -out "cocoa-field-station-${stamp}.tar.gz.enc" \
  -pass env:BACKUP_ENCRYPTION_KEY
```

**How to explain it:** “GitHub Actions is configured to run a database dump once daily or manually. The workflow encrypts the archive before storing it as an artifact, retained for 30 days. It depends on two GitHub repository secrets being configured and a successful workflow run. We still need to test restoring an artifact; a scheduled job is not evidence of recoverability until restore works.”

### Suggested short presentation summary

“I used two factors to reduce the chance that a stolen password is enough to enter the system. Passwords use Argon2id with a unique salt and a private pepper. The PHP API uses parameterized SQL and enforces the user's role on every protected route. Supabase tables are not directly available to the client, and the live model receives only the minimum weather and decision data needed. These controls support confidentiality and integrity; the backup workflow supports availability. I also documented the remaining gaps: public API HTTPS, shared rate limits, account recovery, proof of email ownership for password registration, least-privilege database credentials, and a tested restore.”
