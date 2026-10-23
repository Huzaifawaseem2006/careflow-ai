param([Parameter(Mandatory = $true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
# Read existing current-user trust only; never install or change certificates.
$trusted = Get-ChildItem Cert:\CurrentUser\Root
$certificate = Get-ChildItem Cert:\CurrentUser\My | Where-Object {
    $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) -and
    $_.DnsNameList.Unicode -contains 'localhost' -and
    $_.Thumbprint -in $trusted.Thumbprint
} | Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $certificate) { throw 'No existing trusted current-user localhost certificate. See docs/FRONTEND.md.' }
$directory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($certificate)
try {
    [IO.File]::WriteAllText((Join-Path $directory 'localhost.pem'), $certificate.ExportCertificatePem())
    [IO.File]::WriteAllText((Join-Path $directory 'localhost.key'), $rsa.ExportPkcs8PrivateKeyPem())
} finally { $rsa.Dispose() }
Write-Output 'Exported existing localhost certificate and key; certificate stores unchanged.'
