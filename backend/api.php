<?php
declare(strict_types=1);

session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

$configPath = __DIR__ . '/config.php';
if (!is_file($configPath)) { fail(500, 'Server setup incomplete. Copy config.example.php to config.php.'); }
$config = require $configPath;
try {
    $pdo = new PDO(
        sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_name']),
        $config['db_user'], $config['db_password'],
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_EMULATE_PREPARES => false]
    );
} catch (Throwable $e) { fail(500, 'Database unavailable. Check XAMPP MySQL and backend configuration.'); }

ensure_field_workspace($pdo);

$path = isset($_GET['route']) ? '/' . trim((string)$_GET['route'], '/') : (parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/');
$apiPrefix = '/cocoa-security/api.php';
if (str_starts_with($path, $apiPrefix)) { $path = substr($path, strlen($apiPrefix)); }
$path = '/' . trim($path, '/');
$method = $_SERVER['REQUEST_METHOD'];
$body = json_decode(file_get_contents('php://input') ?: '{}', true);
if (!is_array($body)) { fail(400, 'Request body must be JSON.'); }

if ($method === 'GET' && $path === '/health') {
    echo json_encode(['ok' => true, 'service' => 'Cocoa Field Station security API']); exit;
}

if ($method === 'GET' && $path === '/public-config') {
    echo json_encode(['ok' => true, 'google_web_client_id' => (string)($config['google_web_client_id'] ?? ''), 'google_android_client_id' => (string)($config['google_android_client_id'] ?? ''), 'google_ios_client_id' => (string)($config['google_ios_client_id'] ?? '')]); exit;
}

if ($method === 'POST' && $path === '/register') {
    $name = trim((string)($body['name'] ?? ''));
    $email = strtolower(trim((string)($body['email'] ?? '')));
    $password = (string)($body['password'] ?? '');
    if (mb_strlen($name) < 2 || mb_strlen($name) > 120) { fail(422, 'Enter a name between 2 and 120 characters.'); }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) { fail(422, 'Enter a valid email address.'); }
    if (strlen($password) < 10 || strlen($password) > 1024) { fail(422, 'Use a password between 10 and 1024 characters.'); }
    $hash = password_hash($password . $config['pepper'], PASSWORD_ARGON2ID);
    try {
        $stmt = $pdo->prepare("INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,'user')");
        $stmt->execute([$name, $email, $hash]);
    } catch (PDOException $e) {
        if ($e->getCode() === '23000') { fail(409, 'An account with that email already exists.'); }
        fail(500, 'Could not create the account.');
    }
    http_response_code(201); echo json_encode(['ok' => true, 'message' => 'Account created. Sign in, then connect your authenticator app.']); exit;
}

if ($method === 'POST' && $path === '/login') {
    $email = strtolower(trim((string)($body['email'] ?? '')));
    $password = (string)($body['password'] ?? '');
    $stmt = $pdo->prepare('SELECT id,name,email,password_hash,role,totp_enabled FROM users WHERE email=?');
    $stmt->execute([$email]); $user = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$user || !password_verify($password . $config['pepper'], $user['password_hash'])) { fail(401, 'Email or password is incorrect.'); }
    start_totp_challenge($pdo, $config, $user);
}

if ($method === 'POST' && $path === '/google-login') {
    $idToken = (string)($body['id_token'] ?? '');
    if ($idToken === '' || strlen($idToken) > 10000) { fail(422, 'Google sign-in token is missing.'); }
    try { $claims = verify_google_id_token($idToken, $config); }
    catch (Throwable $e) { fail(401, 'Google sign-in could not be verified. Try again.'); }
    $sub = (string)($claims->sub ?? ''); $email = strtolower((string)($claims->email ?? ''));
    $name = trim((string)($claims->name ?? 'Google user'));
    if ($sub === '' || $email === '' || empty($claims->email_verified)) { fail(401, 'Google did not provide a verified account.'); }
    $stmt = $pdo->prepare('SELECT id,name,email,role,totp_enabled FROM users WHERE google_sub=?');
    $stmt->execute([$sub]); $user = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$user) {
        $stmt = $pdo->prepare('SELECT id FROM users WHERE email=?'); $stmt->execute([$email]);
        if ($stmt->fetchColumn()) { fail(409, 'This email already has a password account. Sign in with its password first.'); }
        try {
            $stmt = $pdo->prepare("INSERT INTO users (name,email,password_hash,role,google_sub) VALUES (?,?,?,'user',?)");
            $stmt->execute([$name !== '' ? mb_substr($name, 0, 120) : 'Google user', $email, password_hash(bin2hex(random_bytes(32)) . $config['pepper'], PASSWORD_ARGON2ID), $sub]);
            $user = ['id' => (int)$pdo->lastInsertId(), 'name' => $name, 'email' => $email, 'role' => 'user', 'totp_enabled' => 0];
        } catch (PDOException $e) { fail(409, 'That Google account could not be linked.'); }
    }
    start_totp_challenge($pdo, $config, $user);
}

if ($method === 'POST' && $path === '/verify-totp') {
    $challengeId = filter_var($body['challenge_id'] ?? null, FILTER_VALIDATE_INT);
    $code = trim((string)($body['code'] ?? ''));
    if (!$challengeId || !preg_match('/^\d{6}$/', $code)) { fail(422, 'Enter the six-digit code.'); }
    $pdo->beginTransaction();
    $stmt = $pdo->prepare('SELECT c.*,u.id AS uid,u.name,u.email,u.role,u.totp_secret_enc,u.totp_enabled FROM login_challenges c JOIN users u ON u.id=c.user_id WHERE c.id=? FOR UPDATE');
    $stmt->execute([$challengeId]); $challenge = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$challenge || $challenge['consumed_at'] !== null || strtotime($challenge['expires_at'] . ' UTC') < time() || (int)$challenge['attempts'] >= 5) {
        $pdo->rollBack(); fail(401, 'Code expired or attempts exceeded. Sign in again for a new code.');
    }
    $encryptedSecret = $challenge['purpose'] === 'totp_setup' ? $challenge['pending_totp_secret_enc'] : $challenge['totp_secret_enc'];
    $secret = $encryptedSecret ? decrypt_totp_secret($encryptedSecret, $config['pepper']) : '';
    if (!verify_totp($secret, $code)) {
        $pdo->prepare('UPDATE login_challenges SET attempts=attempts+1 WHERE id=?')->execute([$challengeId]);
        $pdo->commit(); fail(401, 'That verification code is incorrect.');
    }
    if ($challenge['purpose'] === 'totp_setup') {
        $pdo->prepare('UPDATE users SET totp_secret_enc=?,totp_enabled=1 WHERE id=?')->execute([$challenge['pending_totp_secret_enc'], $challenge['uid']]);
    }
    $pdo->prepare('UPDATE login_challenges SET consumed_at=UTC_TIMESTAMP() WHERE id=?')->execute([$challengeId]);
    $token = bin2hex(random_bytes(32));
    $tokenHash = hash('sha256', $token);
    $pdo->prepare('INSERT INTO api_tokens (user_id,token_hash,expires_at) VALUES (?,?,DATE_ADD(UTC_TIMESTAMP(), INTERVAL 12 HOUR))')
        ->execute([$challenge['uid'], $tokenHash]);
    $pdo->commit();
    echo json_encode(['ok' => true, 'token' => $token, 'user' => ['id' => (int)$challenge['uid'], 'name' => $challenge['name'], 'email' => $challenge['email'], 'role' => $challenge['role']]]); exit;
}

if ($method === 'GET' && $path === '/me') {
    $user = require_user($pdo); echo json_encode(['ok' => true, 'user' => $user]); exit;
}

if ($method === 'POST' && $path === '/logout') {
    $token = bearer_token();
    if ($token) { $pdo->prepare('DELETE FROM api_tokens WHERE token_hash=?')->execute([hash('sha256', $token)]); }
    echo json_encode(['ok' => true]); exit;
}

if ($method === 'GET' && $path === '/admin/users') {
    $user = require_user($pdo);
    if ($user['role'] !== 'admin') { fail(403, 'Admin role required.'); }
    $users = $pdo->query('SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['ok' => true, 'users' => $users]); exit;
}

if ($method === 'GET' && $path === '/field/plots') {
    require_user($pdo);
    $plots = $pdo->query('SELECT plot_id,description FROM field_plots ORDER BY plot_id')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['ok' => true, 'plots' => $plots]); exit;
}

if ($method === 'GET' && $path === '/field/plot') {
    require_user($pdo);
    $plotId = trim((string)($_GET['plot_id'] ?? 'Plot A'));
    $days = min(30, max(7, (int)($_GET['days'] ?? 14)));
    $stmt = $pdo->prepare('SELECT plot_id,description FROM field_plots WHERE plot_id=?');
    $stmt->execute([$plotId]); $plot = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$plot) { fail(404, 'Plot not found.'); }
    $stmt = $pdo->prepare('SELECT observation_date AS date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note FROM field_weather WHERE plot_id=? ORDER BY observation_date DESC LIMIT ?');
    $stmt->bindValue(1, $plotId); $stmt->bindValue(2, $days, PDO::PARAM_INT); $stmt->execute();
    $observations = array_reverse($stmt->fetchAll(PDO::FETCH_ASSOC));
    foreach ($observations as &$row) { foreach (['rainfall_mm','humidity_pct','temp_c'] as $key) $row[$key] = (float)$row[$key]; $row['days_since_last_spray'] = (int)$row['days_since_last_spray']; }
    unset($row);
    $recent = array_slice($observations, -7); $count = count($recent);
    $summary = ['rainfall_7d_mm' => round(array_sum(array_column($recent, 'rainfall_mm')), 1),
        'humidity_7d_pct' => $count ? round(array_sum(array_column($recent, 'humidity_pct')) / $count) : 0,
        'temperature_7d_c' => $count ? round(array_sum(array_column($recent, 'temp_c')) / $count, 1) : 0,
        'latest_date' => $observations ? $observations[count($observations)-1]['date'] : null,
        'completeness_days' => $count];
    echo json_encode(['ok' => true, 'plot' => $plot, 'observations' => $observations, 'summary' => $summary]); exit;
}

if ($method === 'POST' && $path === '/field/recommendation') {
    $user = require_user($pdo);
    $plotId = trim((string)($body['plot_id'] ?? ''));
    $result = create_field_recommendation($pdo, (int)$user['id'], $plotId);
    echo json_encode(['ok' => true, 'recommendation' => $result]); exit;
}

if ($method === 'POST' && $path === '/field/decision') {
    $user = require_user($pdo);
    $decisionId = filter_var($body['decision_id'] ?? null, FILTER_VALIDATE_INT);
    $action = (string)($body['action'] ?? ''); $reason = trim((string)($body['reason'] ?? ''));
    if (!$decisionId || !in_array($action, ['spray','wait','inspect'], true)) { fail(422, 'Select a valid field decision.'); }
    $stmt = $pdo->prepare('SELECT recommendation,human_decision FROM field_decisions WHERE id=? AND user_id=?');
    $stmt->execute([$decisionId, $user['id']]); $decision = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$decision) { fail(404, 'Decision not found.'); }
    if ($decision['human_decision'] !== null) { fail(409, 'This decision has already been recorded.'); }
    if ($action !== $decision['recommendation'] && mb_strlen($reason) < 3) { fail(422, 'Add a short reason when you change the suggestion.'); }
    $stmt = $pdo->prepare('UPDATE field_decisions SET human_decision=?,human_reason=? WHERE id=? AND user_id=? AND human_decision IS NULL');
    $stmt->execute([$action, $reason !== '' ? mb_substr($reason,0,1000) : null, $decisionId, $user['id']]);
    echo json_encode(['ok' => true]); exit;
}

if ($method === 'GET' && $path === '/field/journal') {
    require_user($pdo);
    $plotId = trim((string)($_GET['plot_id'] ?? ''));
    $status = (string)($_GET['status'] ?? 'all');
    $sql = 'SELECT d.id,d.plot_id,d.created_at,d.risk_bucket,d.recommendation,d.rationale,d.evidence_json,d.confidence,d.gated,d.human_decision,d.human_reason,u.name AS grower_name FROM field_decisions d JOIN users u ON u.id=d.user_id WHERE 1=1';
    $params = [];
    if ($plotId !== '' && $plotId !== 'All plots') { $sql .= ' AND d.plot_id=?'; $params[] = $plotId; }
    if ($status === 'pending') $sql .= ' AND d.human_decision IS NULL';
    elseif ($status === 'recorded') $sql .= ' AND d.human_decision IS NOT NULL';
    $sql .= ' ORDER BY d.created_at DESC LIMIT 100';
    $stmt = $pdo->prepare($sql); $stmt->execute($params); $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    foreach ($rows as &$row) { $row['id'] = (int)$row['id']; $row['confidence'] = (float)$row['confidence']; $row['gated'] = (bool)$row['gated']; $row['evidence'] = json_decode((string)$row['evidence_json'], true) ?: []; unset($row['evidence_json']); }
    unset($row);
    echo json_encode(['ok' => true, 'decisions' => $rows]); exit;
}

if ($method === 'GET' && $path === '/field/summary') {
    $user = require_user($pdo);
    $total = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn();
    echo json_encode(['ok' => true, 'message' => 'User workspace', 'signed_in_as' => $user['name'], 'account_count' => $total]); exit;
}

function ensure_field_workspace(PDO $pdo): void {
    $pdo->exec("CREATE TABLE IF NOT EXISTS field_plots (plot_id VARCHAR(40) PRIMARY KEY,description VARCHAR(200) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS field_weather (plot_id VARCHAR(40) NOT NULL,observation_date DATE NOT NULL,rainfall_mm DECIMAL(7,2) NOT NULL,humidity_pct DECIMAL(5,2) NOT NULL,temp_c DECIMAL(5,2) NOT NULL,days_since_last_spray INT NOT NULL,inspection_note VARCHAR(500) NULL,PRIMARY KEY(plot_id,observation_date),CONSTRAINT fk_field_weather_plot FOREIGN KEY(plot_id) REFERENCES field_plots(plot_id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS field_decisions (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,user_id BIGINT UNSIGNED NOT NULL,plot_id VARCHAR(40) NOT NULL,created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,risk_bucket ENUM('low','medium','high') NOT NULL,recommendation ENUM('spray','wait','inspect') NOT NULL,rationale TEXT NOT NULL,evidence_json JSON NOT NULL,confidence DECIMAL(4,3) NOT NULL,gated TINYINT(1) NOT NULL DEFAULT 0,human_decision ENUM('spray','wait','inspect') NULL,human_reason VARCHAR(1000) NULL,CONSTRAINT fk_field_decision_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,CONSTRAINT fk_field_decision_plot FOREIGN KEY(plot_id) REFERENCES field_plots(plot_id),INDEX idx_field_decision_plot_date(plot_id,created_at),INDEX idx_field_decision_user_date(user_id,created_at)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $plots = ['Plot A' => 'Rising rain and humidity', 'Plot B' => 'Recent gaps in observations', 'Plot C' => 'Middle-range conditions'];
    $insertPlot = $pdo->prepare('INSERT IGNORE INTO field_plots(plot_id,description) VALUES(?,?)');
    foreach ($plots as $id => $description) $insertPlot->execute([$id,$description]);
    if ((int)$pdo->query('SELECT COUNT(*) FROM field_weather')->fetchColumn() > 0) return;
    $insertWeather = $pdo->prepare('INSERT IGNORE INTO field_weather(plot_id,observation_date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note) VALUES(?,?,?,?,?,?,?)');
    foreach ($plots as $plot => $_description) {
        for ($ago = 29; $ago >= 0; $ago--) {
            if ($plot === 'Plot B' && in_array($ago, [1,3,5,6], true)) continue;
            $step = 29 - $ago; $n1 = (sin(($step + 1) * 12.9898 + ord($plot[5])) + 1) / 2; $n2 = (sin(($step + 1) * 78.233 + ord($plot[5]) * 0.7) + 1) / 2;
            if ($plot === 'Plot A') { $rain = 2 + $step * 0.25 + $n1 * 1.8; $humidity = min(96, 68 + $step * 0.72 + $n2 * 4); $since = 22 + $ago; }
            elseif ($plot === 'Plot B') { $rain = $n1 * 5; $humidity = 70 + $n2 * 12; $since = 18 + $ago; }
            else { $rain = 2.5 + $n1 * 3; $humidity = 79 + $n2 * 9; $since = 20 + $ago; }
            $temp = 23 + $n1 * 7; $date = gmdate('Y-m-d', time() - $ago * 86400);
            $note = $step % 8 === 0 ? 'Routine simulated field observation.' : null;
            $insertWeather->execute([$plot,$date,round($rain,1),round($humidity,1),round($temp,1),$since,$note]);
        }
    }
}

function create_field_recommendation(PDO $pdo, int $userId, string $plotId): array {
    $stmt = $pdo->prepare('SELECT observation_date AS date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray FROM field_weather WHERE plot_id=? ORDER BY observation_date DESC LIMIT 7');
    $stmt->execute([$plotId]); $days = array_reverse($stmt->fetchAll(PDO::FETCH_ASSOC));
    if (!$days) fail(404, 'Plot observations are not available.');
    $count = count($days); $rain = array_sum(array_map(fn($r)=>(float)$r['rainfall_mm'],$days)); $humidity = array_sum(array_map(fn($r)=>(float)$r['humidity_pct'],$days))/$count; $since = (int)$days[$count-1]['days_since_last_spray'];
    if ($rain >= 50 && $humidity >= 90) { $bucket = 'high'; $suggestion = $since >= 14 ? 'spray' : 'inspect'; }
    elseif ($rain >= 25 || $humidity >= 82) { $bucket = 'medium'; $suggestion = 'inspect'; }
    else { $bucket = 'low'; $suggestion = 'wait'; }
    $confidence = round($count / 7, 3); $gated = $confidence < 0.7; $action = $gated ? 'inspect' : $suggestion;
    $evidence = ['Data completeness: ' . $count . '/7 observations', 'Placeholder rule bucket: ' . $bucket . ' (' . $suggestion . ')', '7-day rainfall: ' . round($rain,1) . ' mm', 'Average humidity: ' . round($humidity) . '%'];
    $rationale = 'Rule-based suggestion from simulated plot observations. Thresholds are illustrative placeholders and need agronomy review. A grower must review the evidence and record the decision; the app never acts on the plot.';
    $stmt = $pdo->prepare('INSERT INTO field_decisions(user_id,plot_id,risk_bucket,recommendation,rationale,evidence_json,confidence,gated) VALUES(?,?,?,?,?,?,?,?)');
    $stmt->execute([$userId,$plotId,$bucket,$action,$rationale,json_encode($evidence),$confidence,(int)$gated]);
    return ['id'=>(int)$pdo->lastInsertId(),'plot_id'=>$plotId,'risk_bucket'=>$bucket,'action'=>$action,'rationale'=>$rationale,'evidence'=>$evidence,'confidence'=>$confidence,'gated'=>$gated,'pending'=>true,'human_decision'=>null,'human_reason'=>null,'ts'=>gmdate(DATE_ATOM)];
}

fail(404, 'Endpoint not found.');

function bearer_token(): ?string {
    $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (!preg_match('/^Bearer\s+([a-f0-9]{64})$/i', $header, $match)) return null;
    return $match[1];
}

function require_user(PDO $pdo): array {
    $token = bearer_token(); if (!$token) fail(401, 'Sign in required.');
    $stmt = $pdo->prepare('SELECT u.id,u.name,u.email,u.role FROM api_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=? AND t.expires_at>UTC_TIMESTAMP()');
    $stmt->execute([hash('sha256', $token)]); $user = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$user) fail(401, 'Session expired. Sign in again.');
    $user['id'] = (int)$user['id']; return $user;
}

function start_totp_challenge(PDO $pdo, array $config, array $user): never {
    $setup = empty($user['totp_enabled']);
    $secret = $setup ? base32_encode(random_bytes(20)) : null;
    $pending = $setup ? encrypt_totp_secret($secret, $config['pepper']) : null;
    $pdo->prepare("INSERT INTO login_challenges (user_id,code_hash,expires_at,purpose,pending_totp_secret_enc) VALUES (?,?,DATE_ADD(UTC_TIMESTAMP(), INTERVAL 10 MINUTE),?,?)")
        ->execute([$user['id'], hash_hmac('sha256', bin2hex(random_bytes(32)), $config['pepper']), $setup ? 'totp_setup' : 'totp_login', $pending]);
    $response = ['ok' => true, 'challenge_id' => (int)$pdo->lastInsertId(), 'setup_required' => $setup];
    if ($setup) {
        $label = rawurlencode('Cocoa Field Station:' . $user['email']);
        $response['secret'] = $secret;
        $response['otpauth_uri'] = 'otpauth://totp/' . $label . '?secret=' . $secret . '&issuer=Cocoa%20Field%20Station&algorithm=SHA1&digits=6&period=30';
    }
    echo json_encode($response); exit;
}

function base32_encode(string $data): string {
    $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; $bits = '';
    foreach (str_split($data) as $char) $bits .= str_pad(decbin(ord($char)), 8, '0', STR_PAD_LEFT);
    $out = ''; foreach (str_split($bits, 5) as $chunk) $out .= $alphabet[bindec(str_pad($chunk, 5, '0'))];
    return $out;
}

function base32_decode(string $value): string {
    $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; $bits = '';
    foreach (str_split(strtoupper(rtrim($value, '='))) as $char) { $n = strpos($alphabet, $char); if ($n === false) throw new RuntimeException('Invalid secret'); $bits .= str_pad(decbin($n), 5, '0', STR_PAD_LEFT); }
    $out = ''; foreach (str_split($bits, 8) as $byte) if (strlen($byte) === 8) $out .= chr(bindec($byte));
    return $out;
}

function verify_totp(string $secret, string $code): bool {
    if ($secret === '' || !preg_match('/^\d{6}$/', $code)) return false;
    $key = base32_decode($secret); $counter = (int)floor(time() / 30);
    for ($offset = -1; $offset <= 1; $offset++) {
        $binary = pack('N2', 0, $counter + $offset); $hash = hash_hmac('sha1', $binary, $key, true); $index = ord($hash[19]) & 0x0f;
        $value = ((ord($hash[$index]) & 0x7f) << 24) | ((ord($hash[$index + 1]) & 0xff) << 16) | ((ord($hash[$index + 2]) & 0xff) << 8) | (ord($hash[$index + 3]) & 0xff);
        if (hash_equals(str_pad((string)($value % 1000000), 6, '0', STR_PAD_LEFT), $code)) return true;
    }
    return false;
}

function totp_key(string $pepper): string { return hash('sha256', 'cocoa-field-station:totp:' . $pepper, true); }
function encrypt_totp_secret(string $secret, string $pepper): string {
    $iv = random_bytes(12); $tag = ''; $cipher = openssl_encrypt($secret, 'aes-256-gcm', totp_key($pepper), OPENSSL_RAW_DATA, $iv, $tag);
    if ($cipher === false) throw new RuntimeException('Encryption failed'); return base64_encode($iv . $tag . $cipher);
}
function decrypt_totp_secret(string $stored, string $pepper): string {
    $raw = base64_decode($stored, true); if ($raw === false || strlen($raw) < 29) return '';
    $plain = openssl_decrypt(substr($raw, 28), 'aes-256-gcm', totp_key($pepper), OPENSSL_RAW_DATA, substr($raw, 0, 12), substr($raw, 12, 16));
    return $plain === false ? '' : $plain;
}

function verify_google_id_token(string $token, array $config): object {
    $clientIds = array_values(array_filter([$config['google_web_client_id'] ?? '', $config['google_android_client_id'] ?? '', $config['google_ios_client_id'] ?? '']));
    if (!$clientIds) throw new RuntimeException('Google OAuth clients not configured.');
    $cacheFile = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'cocoa-google-jwks.json';
    $jwks = is_file($cacheFile) && filemtime($cacheFile) > time() - 3600 ? json_decode((string)file_get_contents($cacheFile), true) : null;
    if (!$jwks) {
        $ctx = stream_context_create(['http' => ['timeout' => 5, 'header' => "Accept: application/json\r\n"]]);
        $raw = @file_get_contents('https://www.googleapis.com/oauth2/v3/certs', false, $ctx);
        $jwks = $raw ? json_decode($raw, true) : null;
        if (!is_array($jwks)) throw new RuntimeException('Google verification keys unavailable.');
        @file_put_contents($cacheFile, json_encode($jwks), LOCK_EX);
    }
    $parts = explode('.', $token);
    if (count($parts) !== 3) throw new RuntimeException('Malformed Google token.');
    $header = json_decode(base64url_decode($parts[0]), true);
    $claimsArray = json_decode(base64url_decode($parts[1]), true);
    $signature = base64url_decode($parts[2]);
    if (!is_array($header) || ($header['alg'] ?? '') !== 'RS256' || !is_array($claimsArray)) throw new RuntimeException('Invalid Google token format.');
    $jwk = null;
    foreach (($jwks['keys'] ?? []) as $candidate) if (($candidate['kid'] ?? '') === ($header['kid'] ?? '') && ($candidate['kty'] ?? '') === 'RSA') { $jwk = $candidate; break; }
    if (!$jwk) throw new RuntimeException('Google signing key not recognized.');
    $key = openssl_pkey_get_public(rsa_jwk_pem($jwk));
    if (!$key || openssl_verify($parts[0] . '.' . $parts[1], $signature, $key, OPENSSL_ALGO_SHA256) !== 1) throw new RuntimeException('Google token signature invalid.');
    $audiences = (array)($claimsArray['aud'] ?? []);
    if (!array_intersect($clientIds, $audiences) || !in_array($claimsArray['iss'] ?? '', ['accounts.google.com', 'https://accounts.google.com'], true) || ($claimsArray['exp'] ?? 0) < time() || ($claimsArray['iat'] ?? PHP_INT_MAX) > time() + 60) throw new RuntimeException('Invalid Google token claims.');
    $claims = (object)$claimsArray;
    return $claims;
}

function base64url_decode(string $value): string {
    $decoded = base64_decode(strtr($value, '-_', '+/') . str_repeat('=', (4 - strlen($value) % 4) % 4), true);
    if ($decoded === false) throw new RuntimeException('Invalid base64url value.');
    return $decoded;
}

function der_length(int $length): string {
    if ($length < 128) return chr($length);
    $bytes = ''; while ($length > 0) { $bytes = chr($length & 0xff) . $bytes; $length >>= 8; }
    return chr(0x80 | strlen($bytes)) . $bytes;
}
function der_element(int $tag, string $data): string { return chr($tag) . der_length(strlen($data)) . $data; }
function der_integer(string $value): string {
    $value = ltrim($value, "\0"); if ($value === '' || (ord($value[0]) & 0x80)) $value = "\0" . $value;
    return der_element(0x02, $value);
}
function rsa_jwk_pem(array $jwk): string {
    $modulus = base64url_decode((string)($jwk['n'] ?? '')); $exponent = base64url_decode((string)($jwk['e'] ?? ''));
    if ($modulus === '' || $exponent === '') throw new RuntimeException('Invalid Google RSA key.');
    $rsa = der_element(0x30, der_integer($modulus) . der_integer($exponent));
    $algorithm = hex2bin('300d06092a864886f70d0101010500');
    $spki = der_element(0x30, $algorithm . der_element(0x03, "\0" . $rsa));
    return "-----BEGIN PUBLIC KEY-----\n" . chunk_split(base64_encode($spki), 64, "\n") . "-----END PUBLIC KEY-----\n";
}

function fail(int $status, string $message): never {
    http_response_code($status); echo json_encode(['ok' => false, 'error' => $message]); exit;
}
