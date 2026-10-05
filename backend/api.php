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

if ($method === 'POST' && $path === '/register') {
    $name = trim((string)($body['name'] ?? ''));
    $email = strtolower(trim((string)($body['email'] ?? '')));
    $password = (string)($body['password'] ?? '');
    if (mb_strlen($name) < 2 || mb_strlen($name) > 120) { fail(422, 'Enter a name between 2 and 120 characters.'); }
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) { fail(422, 'Enter a valid email address.'); }
    if (strlen($password) < 10 || strlen($password) > 1024) { fail(422, 'Use a password between 10 and 1024 characters.'); }
    $hash = password_hash($password . $config['pepper'], PASSWORD_ARGON2ID);
    try {
        $stmt = $pdo->prepare("INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,'Field Officer')");
        $stmt->execute([$name, $email, $hash]);
    } catch (PDOException $e) {
        if ($e->getCode() === '23000') { fail(409, 'An account with that email already exists.'); }
        fail(500, 'Could not create the account.');
    }
    http_response_code(201); echo json_encode(['ok' => true, 'message' => 'Account created. Sign in to verify your email.']); exit;
}

if ($method === 'POST' && $path === '/login') {
    $email = strtolower(trim((string)($body['email'] ?? '')));
    $password = (string)($body['password'] ?? '');
    $stmt = $pdo->prepare('SELECT id,name,email,password_hash,role FROM users WHERE email=?');
    $stmt->execute([$email]); $user = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$user || !password_verify($password . $config['pepper'], $user['password_hash'])) { fail(401, 'Email or password is incorrect.'); }
    $code = (string)random_int(100000, 999999);
    $pdo->prepare('INSERT INTO login_challenges (user_id,code_hash,expires_at) VALUES (?,?,DATE_ADD(UTC_TIMESTAMP(), INTERVAL 10 MINUTE))')
        ->execute([$user['id'], hash_hmac('sha256', $code, $config['pepper'])]);
    try { send_code($config, $user['email'], $user['name'], $code); }
    catch (Throwable $e) { fail(503, 'Could not send the verification code. Check the SMTP settings.'); }
    echo json_encode(['ok' => true, 'challenge_id' => (int)$pdo->lastInsertId(), 'message' => 'A six-digit code was sent to your email.']); exit;
}

if ($method === 'POST' && $path === '/verify') {
    $challengeId = filter_var($body['challenge_id'] ?? null, FILTER_VALIDATE_INT);
    $code = trim((string)($body['code'] ?? ''));
    if (!$challengeId || !preg_match('/^\d{6}$/', $code)) { fail(422, 'Enter the six-digit code.'); }
    $pdo->beginTransaction();
    $stmt = $pdo->prepare('SELECT c.*,u.id AS uid,u.name,u.email,u.role FROM login_challenges c JOIN users u ON u.id=c.user_id WHERE c.id=? FOR UPDATE');
    $stmt->execute([$challengeId]); $challenge = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$challenge || $challenge['consumed_at'] !== null || strtotime($challenge['expires_at'] . ' UTC') < time() || (int)$challenge['attempts'] >= 5) {
        $pdo->rollBack(); fail(401, 'Code expired or attempts exceeded. Sign in again for a new code.');
    }
    $givenHash = hash_hmac('sha256', $code, $config['pepper']);
    if (!hash_equals($challenge['code_hash'], $givenHash)) {
        $pdo->prepare('UPDATE login_challenges SET attempts=attempts+1 WHERE id=?')->execute([$challengeId]);
        $pdo->commit(); fail(401, 'That verification code is incorrect.');
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
    if ($user['role'] !== 'Administrator') { fail(403, 'Administrator role required.'); }
    $users = $pdo->query('SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['ok' => true, 'users' => $users]); exit;
}

if ($method === 'GET' && $path === '/field/summary') {
    $user = require_user($pdo);
    $total = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn();
    echo json_encode(['ok' => true, 'message' => 'Field Officer workspace', 'signed_in_as' => $user['name'], 'account_count' => $total]); exit;
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

function send_code(array $config, string $email, string $name, string $code): void {
    if (!$config['smtp_host'] || !$config['smtp_username'] || !$config['smtp_password']) {
        if (!empty($config['development_log_codes'])) { error_log("Development sign-in code for {$email}: {$code}"); return; }
        throw new RuntimeException('SMTP is not configured.');
    }
    $autoload = __DIR__ . '/vendor/autoload.php';
    if (!is_file($autoload)) throw new RuntimeException('Install PHPMailer using Composer.');
    require_once $autoload;
    $mail = new PHPMailer\PHPMailer\PHPMailer(true);
    $mail->isSMTP(); $mail->Host = $config['smtp_host']; $mail->SMTPAuth = true;
    $mail->Username = $config['smtp_username']; $mail->Password = $config['smtp_password'];
    $mail->SMTPSecure = $config['smtp_encryption'] === 'ssl' ? PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_SMTPS : PHPMailer\PHPMailer\PHPMailer::ENCRYPTION_STARTTLS;
    $mail->Port = (int)$config['smtp_port']; $mail->setFrom($config['mail_from'], 'Cocoa Field Station');
    $mail->addAddress($email, $name); $mail->isHTML(false); $mail->Subject = 'Your Cocoa Field Station verification code';
    $mail->Body = "Your sign-in code is {$code}. It expires in 10 minutes. If you did not request this code, ignore this email.";
    $mail->send();
}

function fail(int $status, string $message): never {
    http_response_code($status); echo json_encode(['ok' => false, 'error' => $message]); exit;
}
