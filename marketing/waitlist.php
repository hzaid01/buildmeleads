<?php
// Open-Source Waitlist Handler with Configurable SMTP Support
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

$input = file_get_contents('php://input');
$data = json_decode($input, true);
$email = '';

if ($data && isset($data['email'])) {
    $email = trim($data['email']);
} elseif (isset($_POST['email'])) {
    $email = trim($_POST['email']);
}

if (empty($email) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Please enter a valid work email.']);
    exit;
}

$date = date('Y-m-d H:i:s T');
$ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';

// 1. Record lead to local CSV ledger
$csv_file = __DIR__ . '/waitlist.csv';
$is_new_file = !file_exists($csv_file);
$fp = @fopen($csv_file, 'a');
if ($fp) {
    if ($is_new_file) {
        fputcsv($fp, ['Email', 'SubmittedAt', 'IPAddress']);
    }
    fputcsv($fp, [$email, $date, $ip]);
    fclose($fp);
}

// 2. Optional SMTP notification dispatch if configured
function send_smtp_email($to, $subject, $body_text) {
    $smtp_host = getenv('SMTP_HOST') ?: '';
    $smtp_port = intval(getenv('SMTP_PORT') ?: 465);
    $smtp_user = getenv('SMTP_USER') ?: '';
    $smtp_pass = getenv('SMTP_PASS') ?: '';

    if (empty($smtp_host) || empty($smtp_user) || empty($smtp_pass)) {
        return false;
    }

    $context = stream_context_create([
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false,
            'allow_self_signed' => true
        ]
    ]);

    $protocol = $smtp_port === 465 ? 'ssl://' : '';
    $socket = @stream_socket_client("{$protocol}{$smtp_host}:{$smtp_port}", $errno, $errstr, 10, STREAM_CLIENT_CONNECT, $context);
    if (!$socket) {
        return false;
    }

    $read = function() use ($socket) {
        $response = '';
        while ($str = fgets($socket, 512)) {
            $response .= $str;
            if (substr($str, 3, 1) === ' ') break;
        }
        return $response;
    };

    $write = function($cmd) use ($socket) {
        fputs($socket, $cmd . "\r\n");
    };

    $read();
    $write("EHLO " . (getenv('PUBLIC_DOMAIN') ?: 'localhost'));
    $read();

    $write("AUTH LOGIN");
    $read();
    $write(base64_encode($smtp_user));
    $read();
    $write(base64_encode($smtp_pass));
    $auth_res = $read();

    if (strpos($auth_res, '235') === false) {
        fclose($socket);
        return false;
    }

    $write("MAIL FROM:<$smtp_user>");
    $read();
    $write("RCPT TO:<$to>");
    $read();
    $write("DATA");
    $read();

    $headers = "From: Lead Scout Notification <$smtp_user>\r\n" .
               "To: <$to>\r\n" .
               "Subject: $subject\r\n" .
               "MIME-Version: 1.0\r\n" .
               "Content-Type: text/plain; charset=UTF-8\r\n" .
               "Date: " . date(DATE_RFC2822) . "\r\n";

    $message = $headers . "\r\n" . $body_text . "\r\n.\r\n";
    $write($message);
    $read();

    $write("QUIT");
    $read();
    fclose($socket);
    return true;
}

$alert_email = getenv('ALERT_EMAIL') ?: (getenv('SMTP_USER') ?: '');
if (!empty($alert_email)) {
    $subject = 'New Waitlist Signup: ' . $email;
    $body = "New waitlist entry received\n\n" .
            "Email: $email\n" .
            "Time:  $date\n" .
            "IP:    $ip\n";
    @send_smtp_email($alert_email, $subject, $body);
}

echo json_encode([
    'success' => true,
    'message' => "You’re on the list — we’ll email you at launch with an exclusive founding-member discount."
]);
