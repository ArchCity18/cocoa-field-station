# Cocoa Field Station · Expo assignment app

An Expo mobile client for the Information Security assignment: identify users, verify sign-in with a second factor, enforce two roles on the server, and store salted password hashes. The companion PHP API is designed for local XAMPP Apache + MySQL.

## What you need

- Node.js LTS and npm
- XAMPP with Apache and MySQL
- Expo Go on a physical phone, or an Android emulator
- Composer only if you want to send real one-time codes over SMTP

## Start the local backend

1. Copy `backend/` from the repository into `C:\xampp\htdocs\cocoa-security\`.
2. Start **Apache** and **MySQL** in the XAMPP Control Panel.
3. Open phpMyAdmin at `http://localhost/phpmyadmin`, import `schema.sql` from the copied backend folder, and confirm the `cocoa_security` database was created.
4. Copy `config.example.php` to `config.php`. Set `pepper` to a private random string. XAMPP defaults often use MySQL user `root` with an empty password; use your own local database credentials if different.
5. Check the API at `http://localhost/cocoa-security/api.php?route=health`; it should return JSON with `"ok":true`.

If you imported an earlier version of this assignment schema, migrate its role labels in phpMyAdmin before using the new `user`/`admin` labels:

```sql
ALTER TABLE users MODIFY role VARCHAR(32) NOT NULL DEFAULT 'user';
UPDATE users SET role = CASE role WHEN 'Administrator' THEN 'admin' WHEN 'Field Officer' THEN 'user' ELSE role END;
ALTER TABLE users MODIFY role ENUM('admin', 'user') NOT NULL DEFAULT 'user';
```

### Enable email one-time codes

The code is generated and checked only by the PHP server; only its keyed hash and expiry are stored. For actual delivery, run `composer install` in the backend folder and set `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_encryption`, and `mail_from` in private `config.php`. Use an email provider's SMTP credentials or app password, not your normal account password. Configure this before using login.

For a local classroom demonstration without SMTP, set `'development_log_codes' => true` in your private `config.php`. The six-digit code is then written to Apache's error log (usually `C:\xampp\apache\logs\error.log`) and is never returned by the API. Do not enable this mode on a network or public server; turn it off immediately after the classroom demo.

## Start the Expo app

From PowerShell:

```powershell
cd C:\Users\Archilles\Documents\Hackathon\mobile
npm install
```

Set the API URL in `src/api.js`:

- Android emulator: `http://10.0.2.2/cocoa-security/api.php`
- iOS simulator: `http://localhost/cocoa-security/api.php`
- Physical phone: `http://YOUR-COMPUTER-LAN-IP/cocoa-security/api.php` (phone and computer must be on the same Wi-Fi; allow Apache through Windows Firewall for Private networks)

Then start Expo:

```powershell
npm start
```

Scan the QR code with Expo Go. Your computer and phone must be on the same network. XAMPP/Expo local development uses HTTP; use HTTPS and restrict CORS before exposing the API outside localhost/LAN.

## Try both roles

1. Create an account; registration always assigns the **user** role. The app refuses passwords under 10 characters. This account can use `/field/summary` but cannot access the admin directory.
2. Sign in with that email/password. Enter the one-time code received by email (or read the local Apache error log in development-only mode).
3. To demonstrate **admin**, register a second account, then promote that account from phpMyAdmin using a known email:

   ```sql
   UPDATE users SET role='admin' WHERE email='trusted-admin@example.com';
   ```

4. Sign in as that account. It can open the user directory endpoint; the API denies that route to a `user` token even if the user tries to call it directly.

Never make public account registration grant `admin` privileges. Promote only a trusted account through a protected setup process/database operation.
