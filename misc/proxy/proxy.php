<?php
$target_base = 'https://quest.ms.mff.cuni.cz/ltb/';

$clean_uri = preg_replace('#^/ltb/#', '/', $_SERVER['REQUEST_URI']);
$target_url = $target_base . ltrim($clean_uri, '/');

$ch = curl_init($target_url);
$method = $_SERVER['REQUEST_METHOD'];
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);

$headers = [];
$strip_req_headers = ['host', 'accept-encoding', 'connection'];

foreach ($_SERVER as $k => $v) {
    if (strpos($k, 'HTTP_') === 0) {
        $name = str_replace('_', '-', substr($k, 5));
        if (in_array(strtolower($name), $strip_req_headers))
            continue;
        $headers[] = "$name: $v";
    } elseif ($k === 'CONTENT_TYPE') {
        $headers[] = "Content-Type: $v";
    }
}
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

if (in_array($method, ['POST', 'PUT', 'PATCH', 'DELETE'])) {
    $body = file_get_contents('php://input');
    if (!empty($body))
        curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, true);
curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 2);

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$header_size = curl_getinfo($ch, CURLINFO_HEADER_SIZE);

// curl_close is omitted; object lifecycle is handled by PHP garbage collection.

if ($response === false) {
    http_response_code(502);
    die('Bad Gateway');
}

http_response_code($http_code);

$res_headers = explode("\r\n", substr($response, 0, $header_size));
$strip_res_headers = ['transfer-encoding', 'connection', 'content-encoding'];

foreach ($res_headers as $hdr) {
    $hdr = trim($hdr);
    if (empty($hdr) || preg_match('#^HTTP/(1\.0|1\.1|2|3)\s+\d{3}#i', $hdr))
        continue;

    $parts = explode(':', $hdr, 2);
    if (count($parts) === 2) {
        $name = strtolower(trim($parts[0]));
        if (in_array($name, $strip_res_headers))
            continue;
        header($hdr, true);
    }
}

echo substr($response, $header_size);
?>