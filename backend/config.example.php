<?php
// Copy to config.php, then set a long random pepper and OAuth client IDs.
return [
    'db_host' => '127.0.0.1',
    'db_name' => 'cocoa_security',
    // Create this restricted MySQL account using the SQL in mobile/README.md.
    'db_user' => 'cocoa_app',
    'db_password' => 'REPLACE_WITH_A_LONG_RANDOM_DATABASE_PASSWORD',
    'pepper' => 'REPLACE_WITH_A_LONG_RANDOM_SECRET',
    // Add the Expo web origin used during local development or hosting.
    'allowed_origins' => ['http://localhost:8081', 'http://127.0.0.1:8081'],
    'google_web_client_id' => '',
    'google_android_client_id' => '',
    'google_ios_client_id' => '',
];
