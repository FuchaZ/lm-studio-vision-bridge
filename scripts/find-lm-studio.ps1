# Find-LMStudio.ps1 — probe localhost + every NIC IP:1234, return first hit
$port = 1234
@("http://127.0.0.1:$port","http://localhost:$port") + (
  [System.Net.Dns]::GetHostEntry([System.Net.Dns]::GetHostName()).AddressList |
    Where-Object AddressFamily -eq InterNetwork |
    Where-Object { $_.IPAddressToString -ne '127.0.0.1' } |
    ForEach-Object { "http://$($_.IPAddressToString):$port" }
) | ForEach-Object {
  try { $r = [System.Net.WebRequest]::Create("$_/v1/models"); $r.Timeout=1500; $resp=$r.GetResponse(); $resp.Close()
    "Found: $_" } catch {} } | Select-Object -First 1
