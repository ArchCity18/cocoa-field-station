CREATE DATABASE IF NOT EXISTS cocoa_security CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cocoa_security;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(512) NOT NULL,
    role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    google_sub VARCHAR(255) NULL UNIQUE,
    totp_secret_enc TEXT NULL,
    totp_enabled TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS login_challenges (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    code_hash CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
    consumed_at DATETIME NULL,
    purpose ENUM('totp_setup', 'totp_login') NOT NULL DEFAULT 'totp_login',
    pending_totp_secret_enc TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_login_challenge_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_challenge_user (user_id, created_at)
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_api_token_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token_user (user_id)
);

CREATE TABLE IF NOT EXISTS field_plots (
    plot_id VARCHAR(40) NOT NULL PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

CREATE TABLE IF NOT EXISTS field_weather (
    plot_id VARCHAR(40) NOT NULL,
    observation_date DATE NOT NULL,
    rainfall_mm DECIMAL(7,2) NOT NULL,
    humidity_pct DECIMAL(5,2) NOT NULL,
    temp_c DECIMAL(5,2) NOT NULL,
    days_since_last_spray INT NOT NULL,
    inspection_note VARCHAR(500) NULL,
    PRIMARY KEY (plot_id, observation_date),
    CONSTRAINT fk_field_weather_plot FOREIGN KEY (plot_id) REFERENCES field_plots(plot_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS field_decisions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    plot_id VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    risk_bucket ENUM('low', 'medium', 'high') NOT NULL,
    recommendation ENUM('spray', 'wait', 'inspect') NOT NULL,
    rationale TEXT NOT NULL,
    evidence_json JSON NOT NULL,
    confidence DECIMAL(4,3) NOT NULL,
    gated TINYINT(1) NOT NULL DEFAULT 0,
    human_decision ENUM('spray', 'wait', 'inspect') NULL,
    human_reason VARCHAR(1000) NULL,
    CONSTRAINT fk_field_decision_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_field_decision_plot FOREIGN KEY (plot_id) REFERENCES field_plots(plot_id),
    INDEX idx_field_decision_plot_date (plot_id, created_at),
    INDEX idx_field_decision_user_date (user_id, created_at)
);

-- Grant admin only to a trusted account through SQL after registration.
-- Example: UPDATE users SET role='admin' WHERE email='admin@example.com';
