# Design and Implementation of a Role-Based Two-Factor Login System

**Project:** Cocoa Field Station

**Course:** Information Security  |  **Prepared by:** ____________________

**Date:** 7 October 2026

## 1. Purpose and system overview

This practical project implements an authentication and access-control system for a cocoa field-record application. Its aims are to identify each account, verify identity with two factors, restrict actions by role, protect password records, and keep a local database connection under controlled access. The same user experience is delivered through two independent clients: a Streamlit web application and an Expo React Native application. They do not share a database or login session.

The Streamlit client runs with `streamlit run app.py`; Google OpenID Connect verifies the account and Google Authenticator TOTP supplies the second factor. Account and TOTP-enrollment records reside in a local SQLite file. Google retains and verifies the user's Google password, so Streamlit never receives or stores it. The Expo client is built with React Native. It communicates over JSON with a PHP API hosted by Apache in XAMPP; MySQL stores the account, challenge, session, plot, and audit data. XAMPP is the local server environment.

## 2. Identification and authentication

The system uses a stable Google subject and verified email to identify a Streamlit user. Expo additionally supports local accounts identified by a normalized email address. The Google option verifies Google's signed ID token on the PHP server and uses its subject as the external identity. A Google password is not collected by either client.

After Google sign-in in Streamlit, or password/Google sign-in in Expo, a user must enroll in or enter a time-based one-time password (TOTP). During enrollment the app displays a QR code and a manual key for Google Authenticator or another compatible authenticator. A valid six-digit code is checked for the current time step and a small clock-skew window. Expo challenges expire after ten minutes and allow up to five attempts. Successful Expo authentication creates a time-limited bearer session; only its SHA-256 digest is stored in MySQL. Logout revokes the token. Streamlit encrypts its TOTP enrollment secret before placing it in SQLite; the cookie secret must be kept private and stable.

## 3. Password storage and database protection

For Expo password accounts, PHP `password_hash` with `PASSWORD_ARGON2ID` generates a unique random salt and stores the salt, algorithm, and cost metadata alongside each password hash. A private server-side pepper is added before hashing. Login uses `password_verify`; plaintext passwords are never written to the database. The pepper is kept in the untracked XAMPP `backend/config.php`, outside the mobile client. Google-only accounts receive a random, unusable local password hash rather than a Google password.

The PHP API uses PDO parameterized statements with emulated prepares disabled. Its MySQL account is intended to have only `SELECT`, `INSERT`, `UPDATE`, and `DELETE` rights on `cocoa_security`; schema changes are applied once by an administrator through phpMyAdmin. Configuration and secrets are separate from public code. Streamlit uses SQLite for its local web demo; its hosted Community Cloud database remains separate from XAMPP. Once installed, both local databases work without a cloud database service, although Google sign-in requires internet access. Local databases are not encrypted at rest by this prototype, so operating-system access controls and protected backups remain necessary.

## 4. Frontend, backend, and data flow

The frontend frameworks are Streamlit (web) and Expo/React Native (mobile and web). The Expo API is PHP 8.1 or later with MySQL; Apache and MySQL run locally through XAMPP. Plot observations are shared among authorized app users within each application's own database. New observation rows record the entering user's identity. Decision recommendations remain human-reviewed; sample weather and thresholds are illustrative and not agronomic advice.

**Request flow:** User → Streamlit or Expo client → Google identity / local credentials → TOTP challenge → authorized session → SQLite (web) or PHP/PDO → local MySQL (Expo).

## 5. Role authorization and access balance

Authorization is enforced in the protected application functions and, for Expo, again by the PHP API on every protected request. The interface hides unavailable actions for clarity, but hidden buttons are not treated as a security boundary. Open registration always creates the least-privileged inputer role; trusted operators assign elevated roles through Streamlit Secrets or local database administration.

| Role | Enter observations | Add inputers | Remove inputers |
| --- | --- | --- | --- |
| Inputer | Yes | No | No |
| Manager | Yes | Yes | No |
| Admin | No | No | Yes |
| Administrator | Yes | Yes | Yes |

Managers invite an inputer by name and email; the person activates access by registering with that same identity. Admins can remove only inputer accounts, never other privileged roles. Expo deactivates the account and revokes its sessions while retaining its field history. Streamlit removes the active account and blocks the Google identity until a manager issues a new invitation. These controls limit account-management power while allowing field staff to record observations and managers to provision workers.

## 6. Implementation status and limitations

The required identification, two-factor authentication, four roles, salted/peppered password hashing (for Expo password accounts), frontends, separate databases, protected database credentials, local servers, and human-readable permission boundaries are implemented. A migration script updates an existing XAMPP database; fresh installations use the complete schema. Static verification includes Python syntax compilation, PHP syntax lint, Expo web export, and Git whitespace checks; the unit test suite was not run.

This is a local coursework prototype. XAMPP traffic is HTTP and should stay on localhost or a trusted private LAN. Public operation requires HTTPS, strict deployment-specific origins, rate limiting, secure backup and recovery procedures, and durable hosted database service. Streamlit Community Cloud does not connect to the local XAMPP MySQL database. The TOTP second factor mitigates password-only compromise but does not replace device security, access reviews, or secure recovery. Deployment secrets must never be committed or included in a report.
