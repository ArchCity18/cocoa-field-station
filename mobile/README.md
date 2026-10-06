# Cocoa Field Station Expo assignment app

Expo client and PHP/MySQL backend for a coursework login system with user identification, Google Authenticator TOTP two-factor authentication, Google sign-in, server-enforced user and admin roles, and Argon2id password hashes with per-password salts and a server pepper.

## Requirements

- Node.js LTS and npm
- XAMPP Apache and MySQL
- Expo Go for local UI testing; OAuth on Android/iOS requires an Expo development build
- Google OAuth client ID for the Expo web origin

## Run the PHP API in XAMPP

1. Copy the contents of backend/ into C:\xampp\htdocs\cocoa-security\, so api.php is directly inside that folder.
2. Start Apache and MySQL in the XAMPP Control Panel.
3. Import schema.sql in http://localhost/phpmyadmin to create cocoa_security.
4. Copy config.example.php to config.php. Set a long random pepper and Google OAuth client IDs. Keep config.php private and out of Git.
5. Visit http://localhost/cocoa-security/api.php?route=health; it should return JSON with ok:true. The updated API creates the plot, observation, and decision tables on first request and seeds clearly simulated observations for Plot A, Plot B, and Plot C.

If you already imported an earlier database, run backend/migrations/002_google_totp.sql once in phpMyAdmin. Back up the database first. This migration adds the Google account identifier and encrypted TOTP secret columns.

## Configure Google sign-in

In Google Cloud Console, create an OAuth client with application type Web application. Start Expo web and copy the exact local redirect URI shown under the Continue with Google button. Add its origin under Authorized JavaScript origins and the full URI under Authorized redirect URIs. Put the client ID in google_web_client_id in the XAMPP config.php. Do not put a client secret in the Expo app. The PHP server checks Google's signed ID token before creating or finding the account.

Google sign-in creates a user account when needed and then also requires a TOTP code. For native Android/iOS sign-in, configure platform-specific OAuth clients in config.php and run an Expo development build; Expo Go cannot complete native OAuth. See https://docs.expo.dev/guides/authentication/ and https://developers.google.com/identity/openid-connect/openid-connect.

## Run the Expo app

    cd C:\Users\Archilles\Documents\Hackathon\mobile
    npm install
    npm start

For the browser build, run npm run web. The API URL in src/api.js is configured for Android emulator, iOS simulator, and web on the same computer. For a physical phone, replace localhost with your computer's LAN IP and allow Apache through Windows Firewall on a private network.

After creating an account, sign in with email and password. The first successful login shows a QR code and a manual setup key; scan it in Google Authenticator, then enter the current six-digit code to finish enrollment. Later logins ask for the current code. The TOTP secret is encrypted in MySQL using a key derived from the private server pepper. A challenge expires in ten minutes and allows at most five attempts.

After TOTP verification, the app opens the field workspace: plot monitor, recent observation trends, rule-based suggestions for human review, and the decision journal. Admin accounts also see the account directory. These Expo records are stored in the XAMPP `cocoa_security` MySQL database. They are separate from the Streamlit Community Cloud demo and its SQLite data, so updates and decisions do not sync between the two apps. The Expo rule suggestions are a transparent PHP placeholder; they do not call the Streamlit model. All weather is simulated and thresholds are unverified examples, not farm advice.

## Demonstrate role authorization

New registrations always receive the user role. To promote a trusted account for the assignment demonstration, use phpMyAdmin:

    UPDATE users SET role='admin' WHERE email='trusted-admin@example.com';

The admin can open the account directory; the API returns 403 for a user token calling that route directly. Never grant admin through public registration.

## Security notes

This is a local coursework prototype. Keep the XAMPP API on localhost or a trusted LAN. Public deployment requires HTTPS, restrictive CORS, request throttling, secure secret management, and a reviewed account recovery process. Do not reuse a Streamlit OAuth redirect URI for Expo; register each app origin/callback with its Google OAuth client.
