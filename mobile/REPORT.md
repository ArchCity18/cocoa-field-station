# Information Security Assignment Report

## Objective

Build a mobile application that demonstrates user identification, two-factor authentication, role-based authorization for two roles, and salted password storage, using Expo with a local server/database stack.

## System design

The Expo React Native client is the presentation layer. It communicates with a PHP JSON API hosted by Apache in XAMPP. MySQL stores users, one-time-code challenges, and revocable API-token hashes. The server is trusted: it validates input, checks credentials, issues and consumes verification codes, creates sessions, and enforces role permissions for every protected route. The app stores only the opaque session token in device SecureStore; passwords and one-time codes are never persisted on-device.

### User identification

Registration requires a name, unique email address, and a password. Email is normalized to lowercase and stored as the account identifier. Database queries use PDO prepared statements. Registration always assigns the least-privileged Field Officer role; an Administrator must be promoted by a trusted operator.

### Two-factor authentication

After the password check, the server generates a cryptographically random six-digit code, stores only an HMAC-SHA256 digest with a ten-minute expiry, and sends the code to the registered email through SMTP. Verification allows at most five attempts and the challenge is consumed once. On success, the server issues a random 256-bit bearer token with a twelve-hour expiry and stores only its SHA-256 digest. Logout revokes the token. SMTP credentials are kept in the ignored local `backend/config.php`.

For classroom operation without configured SMTP, a development-only mode writes the code to Apache's error log. This mode is disabled by default and must not be used on a public server.

### Authorization and roles

The two roles are **Administrator** and **Field Officer**. Both can use the field summary; only Administrator can use the account directory. Role checks happen inside each PHP route after the token is validated, so hiding a screen in React Native cannot grant access. Public registration cannot choose a role. The initial trusted administrator is promoted out-of-band through local database administration.

### Salted password storage

PHP `password_hash` with `PASSWORD_ARGON2ID` creates a unique random salt for each password and performs a deliberately expensive password hash. The encoded salt, algorithm, and work parameters are stored with the hash in `users.password_hash`; no plaintext password is stored. A server-side pepper in private configuration is appended before hashing. Login uses `password_verify`, which reads the encoded per-user salt/parameters. Database compromise alone therefore does not reveal the original passwords, though secrets and database access still require protection.

## Implementation files

- `mobile/src/App.js`: responsive sign-in, account creation, verification, Field Officer home, and Administrator directory screens.
- `mobile/src/api.js`: API client and opaque token persistence in Expo SecureStore.
- `backend/api.php`: registration, login, email challenge, verification, logout, session lookup, and role-protected routes.
- `backend/schema.sql`: MySQL users, challenges, and token tables.
- `backend/config.example.php`: sample local DB, SMTP, and pepper configuration. The real `config.php` must remain private.

## How to run and demonstrate

1. Import `backend/schema.sql` in XAMPP phpMyAdmin and run Apache and MySQL.
2. Configure private `backend/config.php`; configure SMTP for actual delivery, or use the development-only Apache-log code setting in a private local environment.
3. Set the Expo API URL to the XAMPP computer address, run `npm install` and `npm start` in `mobile/`, and open in Expo Go.
4. Register a Field Officer, sign in, and complete the emailed code step.
5. Promote a trusted second account to Administrator using the documented SQL, sign in, and demonstrate the directory. Call the admin route with a Field Officer token to observe the server-side `403` denial.
6. Inspect the database: password values are Argon2id encoded hashes, challenges contain digests rather than codes, and sessions contain token digests rather than bearer tokens.

## Security limitations and next improvements

This is a local coursework prototype, not a production identity platform. Its local XAMPP deployment uses HTTP; public deployments must use HTTPS, restrict CORS, add request throttling and audit events, protect administrator promotion, and use a managed secret store. Email OTP is weaker than TOTP or passkeys and depends on securing the email account. Session tokens use Expo SecureStore. Password reset, account recovery, device/session management, backup, privacy retention, and automated security testing are outside this assignment prototype. Development log-code mode must remain disabled outside an isolated classroom machine.
