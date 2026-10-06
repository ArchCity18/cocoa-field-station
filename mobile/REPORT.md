# Information Security Assignment Report

## Objective

Build a mobile application demonstrating user identification, two-factor authentication, role-based authorization for user and admin, and salted password storage, using Expo with a local server and database.

## System design

The Expo React Native client communicates with a PHP JSON API hosted by Apache in XAMPP. MySQL stores accounts, short-lived authentication challenges, and hashed API session tokens. The server validates credentials, verifies time-based one-time passwords, issues sessions, validates Google ID tokens, and enforces role permissions. The mobile app stores only an opaque session token in Expo SecureStore.

## User identification and Google sign-in

Password accounts are identified by normalized email. The optional Continue with Google flow sends Google's ID token to the PHP API. The API verifies its RS256 signature against Google's published keys and checks issuer, audience, expiry, and verified email. The stable Google subject identifies linked Google accounts. Registration through either method receives only the user role. Existing password accounts are not silently linked by matching email.

## Two-factor authentication

After password or Google identification, the API starts a ten-minute TOTP challenge. New accounts receive a random authenticator secret and an otpauth URI, shown as a QR code with a manual setup key. The user scans this using Google Authenticator or another TOTP app, then confirms a six-digit code. Later sign-ins require a current TOTP code. Verification follows RFC 6238 with a small clock-skew window, allows at most five failed attempts, and consumes a successful challenge once.

The TOTP secret is encrypted using AES-256-GCM with a key derived from the private server pepper before it is stored in MySQL. Codes are never stored. After verification, the server generates a random 256-bit bearer token, stores only its SHA-256 digest, and returns the token to the client. Tokens expire after twelve hours; logout revokes them.

## Authorization and roles

The roles are user and admin. Both can use the field summary; only admin can open the account directory. Role checks happen in PHP after validating each token, so hiding a client screen cannot grant access. Public registration cannot assign admin. A trusted operator promotes the designated demonstration account out-of-band through local database administration.

## Salted password storage

PHP password_hash with PASSWORD_ARGON2ID creates a unique random salt for each password. The encoded salt, algorithm, and work parameters are stored with the hash in users.password_hash; plaintext passwords are never stored. A private server-side pepper is appended before hashing.

## Implementation files

- mobile/src/App.js: registration, password and Google sign-in, TOTP enrollment, user home, and admin directory.
- mobile/src/api.js: API client and session token persistence using Expo SecureStore.
- backend/api.php: registration, password and Google login, TOTP verification, token sessions, and role-protected routes.
- backend/schema.sql: MySQL account, challenge, and token tables.
- backend/migrations/002_google_totp.sql: schema update for an existing database.
- backend/config.example.php: sample local database, pepper, and OAuth client ID configuration. Keep the real config.php private.

## Demonstration

1. Import backend/schema.sql in phpMyAdmin, configure the private backend/config.php, and start XAMPP Apache and MySQL.
2. Register a user, sign in, scan the QR code in Google Authenticator, and enter the displayed code.
3. Sign out and sign in again to demonstrate the authenticator challenge.
4. Register or sign in with Google after configuring the OAuth web client; that account also completes TOTP enrollment and verification.
5. Promote a trusted account to admin in phpMyAdmin and demonstrate its account directory. Use a user token against the admin route to show the server returns 403.
6. Inspect MySQL to confirm passwords and session tokens are stored as hashes and TOTP secrets are encrypted.

## Limitations

This local coursework prototype uses HTTP and wildcard CORS for local development. A public deployment needs HTTPS, restricted CORS, request throttling, protected admin provisioning, secure secret management, backups, and a reviewed account recovery process. Expo Go cannot finish native Google OAuth; use a development build with Android/iOS OAuth clients. If the server pepper is lost, encrypted TOTP secrets cannot be decrypted and users must reenroll.
