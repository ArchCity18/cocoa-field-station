<?php
// Copy to config.php, then set a long random pepper and OAuth client IDs.
return [
    // For Supabase, use the Session Pooler connection string and the Postgres
    // driver. Keep the complete DSN and password in the private config.php.
    // XAMPP's MySQL setup remains available for local-only development.
    'db_driver' => 'mysql', // Change to 'pgsql' after enabling PDO_PGSQL.
    'db_host' => '127.0.0.1',
    'db_name' => 'cocoa_security',
    'db_port' => 3306,
    'db_dsn' => '', // Example: pgsql:host=...;port=5432;dbname=postgres;sslmode=require
    // MySQL local mode: use the restricted cocoa_app account from the README.
    // Supabase mode: fill these with the Session Pooler username/password.
    'db_user' => 'cocoa_app',
    'db_password' => 'REPLACE_WITH_A_LONG_RANDOM_DATABASE_PASSWORD',
    'pepper' => 'REPLACE_WITH_A_LONG_RANDOM_SECRET',
    // Add the Expo web origin used during local development or hosting.
    'allowed_origins' => ['http://localhost:8081', 'http://127.0.0.1:8081'],
    'google_web_client_id' => '',
    'google_android_client_id' => '',
    'google_ios_client_id' => '',
];
