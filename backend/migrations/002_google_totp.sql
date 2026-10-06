-- Apply once to an existing cocoa_security database after backing it up.
ALTER TABLE users
    ADD COLUMN google_sub VARCHAR(255) NULL UNIQUE AFTER role,
    ADD COLUMN totp_secret_enc TEXT NULL AFTER google_sub,
    ADD COLUMN totp_enabled TINYINT(1) NOT NULL DEFAULT 0 AFTER totp_secret_enc;

ALTER TABLE login_challenges
    ADD COLUMN purpose ENUM('totp_setup', 'totp_login') NOT NULL DEFAULT 'totp_login' AFTER consumed_at,
    ADD COLUMN pending_totp_secret_enc TEXT NULL AFTER purpose;
