-- Back up cocoa_security in phpMyAdmin before running this once.
-- Apply after 002_google_totp.sql on an existing database. Fresh databases
-- should import backend/schema.sql instead.
USE cocoa_security;

-- Keep legacy role values valid while converting the old `user` role.
ALTER TABLE users MODIFY role ENUM('user','inputer','admin','administrator','manager') NOT NULL DEFAULT 'inputer';
UPDATE users SET role='inputer' WHERE role='user';
ALTER TABLE users MODIFY role ENUM('inputer','admin','administrator','manager') NOT NULL DEFAULT 'inputer';
-- The earlier API version may already have added is_active at request time.
SET @has_is_active = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='users' AND COLUMN_NAME='is_active'
);
SET @add_is_active = IF(@has_is_active=0,
    'ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER role',
    'SELECT 1');
PREPARE stmt FROM @add_is_active; EXECUTE stmt; DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS field_plots (
    plot_id VARCHAR(40) NOT NULL PRIMARY KEY,
    description VARCHAR(200) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS field_weather (
    plot_id VARCHAR(40) NOT NULL,
    observation_date DATE NOT NULL,
    rainfall_mm DECIMAL(7,2) NOT NULL,
    humidity_pct DECIMAL(5,2) NOT NULL,
    temp_c DECIMAL(5,2) NOT NULL,
    days_since_last_spray INT NOT NULL,
    inspection_note VARCHAR(500) NULL,
    entered_by BIGINT UNSIGNED NULL,
    PRIMARY KEY (plot_id, observation_date),
    CONSTRAINT fk_field_weather_plot FOREIGN KEY (plot_id) REFERENCES field_plots(plot_id) ON DELETE CASCADE,
    CONSTRAINT fk_field_weather_user FOREIGN KEY (entered_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The earlier prototype may already have field_weather without entered_by.
-- Add the column and audit foreign key only when they are missing.
SET @has_entered_by = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='field_weather' AND COLUMN_NAME='entered_by'
);
SET @add_entered_by = IF(@has_entered_by=0,
    'ALTER TABLE field_weather ADD COLUMN entered_by BIGINT UNSIGNED NULL',
    'SELECT 1');
PREPARE stmt FROM @add_entered_by; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_weather_user_fk = (
    SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='field_weather'
      AND CONSTRAINT_NAME='fk_field_weather_user' AND CONSTRAINT_TYPE='FOREIGN KEY'
);
SET @add_weather_user_fk = IF(@has_weather_user_fk=0,
    'ALTER TABLE field_weather ADD CONSTRAINT fk_field_weather_user FOREIGN KEY (entered_by) REFERENCES users(id) ON DELETE SET NULL',
    'SELECT 1');
PREPARE stmt FROM @add_weather_user_fk; EXECUTE stmt; DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS field_decisions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    plot_id VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    risk_bucket ENUM('low','medium','high') NOT NULL,
    recommendation ENUM('spray','wait','inspect') NOT NULL,
    rationale TEXT NOT NULL,
    evidence_json JSON NOT NULL,
    confidence DECIMAL(4,3) NOT NULL,
    gated TINYINT(1) NOT NULL DEFAULT 0,
    human_decision ENUM('spray','wait','inspect') NULL,
    human_reason VARCHAR(1000) NULL,
    CONSTRAINT fk_field_decision_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_field_decision_plot FOREIGN KEY (plot_id) REFERENCES field_plots(plot_id),
    INDEX idx_field_decision_plot_date (plot_id, created_at),
    INDEX idx_field_decision_user_date (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inputer_invites (
    email VARCHAR(254) NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    invited_by BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_invite_manager FOREIGN KEY (invited_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO field_plots(plot_id,description) VALUES
    ('Plot A','Rising rain and humidity'),
    ('Plot B','Recent gaps in observations'),
    ('Plot C','Middle-range conditions');
