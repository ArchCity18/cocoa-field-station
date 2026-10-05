<?php
// Copy to config.php, then set a long random pepper and SMTP credentials.
return [
    'db_host' => '127.0.0.1',
    'db_name' => 'cocoa_security',
    'db_user' => 'root',
    'db_password' => '',
    'pepper' => 'REPLACE_WITH_A_LONG_RANDOM_SECRET',
    'mail_from' => 'field-station@example.test',
    'smtp_host' => '',
    'smtp_port' => 587,
    'smtp_username' => '',
    'smtp_password' => '',
    'smtp_encryption' => 'tls',
    'development_log_codes' => false,
];
