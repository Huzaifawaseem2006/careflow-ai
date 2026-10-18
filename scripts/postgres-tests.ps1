[CmdletBinding()]
param(
    [ValidateSet('setup', 'validate', 'test', 'rotate', 'delete')]
    [string]$Command = 'validate',
    [string[]]$TestPath = @('backend/integration_tests')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-CredentialDirectory {
    Join-Path ([Environment]::GetFolderPath('UserProfile')) '.careflow-ai'
}

function Assert-NoReparsePoint([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    while ($null -ne $item) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Credential paths must not contain links or reparse points.'
        }
        if ($item -is [IO.DirectoryInfo]) { $item = $item.Parent } else { $item = $item.Directory }
    }
}

function Get-CredentialAcl([IO.FileSystemInfo]$Item) {
    $sections = [Security.AccessControl.AccessControlSections]'Access,Owner'
    if ($PSVersionTable.PSEdition -eq 'Core') {
        return [IO.FileSystemAclExtensions]::GetAccessControl($Item, $sections)
    } else {
        return $Item.GetAccessControl($sections)
    }
}

function Set-PrivateAcl([string]$Path, [bool]$Directory) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $item = Get-Item -LiteralPath $Path
    $acl = Get-CredentialAcl $item
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($existing in @($acl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))) {
        $acl.RemoveAccessRuleSpecific($existing)
    }
    if ($Directory) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    } else {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
    }
    $acl.SetOwner($sid)
    $acl.AddAccessRule($rule)
    if ($PSVersionTable.PSEdition -eq 'Core') {
        [IO.FileSystemAclExtensions]::SetAccessControl($item, $acl)
    } else {
        $item.SetAccessControl($acl)
    }
}

function Assert-PrivateAcl([string]$Path) {
    Assert-NoReparsePoint $Path
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $acl = Get-CredentialAcl (Get-Item -LiteralPath $Path)
    if (-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid) {
        throw 'Credential permissions are unsafe; delete and set up again.'
    }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 1 -or $rules[0].IdentityReference.Value -ne $sid -or
        $rules[0].AccessControlType -ne 'Allow' -or $rules[0].FileSystemRights -ne 'FullControl') {
        throw 'Credential permissions are unsafe; delete and set up again.'
    }
}

function Invoke-CredentialProcess($Credential, [string]$Action, [string[]]$Paths) {
    if ($Credential -isnot [Management.Automation.PSCredential] -or $Credential.UserName -cne 'postgres' -or $Credential.Password.Length -eq 0) {
        throw 'Invalid stored credential; rotate or set up again.'
    }
    $root = Split-Path $PSScriptRoot -Parent
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Install the project virtual environment first.' }
    foreach ($path in $Paths) {
        if ($path -cnotmatch '^backend/integration_tests(?:/test_[a-z0-9_]+\.py(?:::[a-zA-Z0-9_]+)?)?$') {
            throw 'Only integration-test paths and individual test functions are accepted.'
        }
    }
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $python
    $start.WorkingDirectory = $root
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    # All arguments are fixed or constrained above; secrets never enter arguments.
    $start.Arguments = '-I scripts/postgres_test_runner.py ' + $Action + ' ' + ($Paths -join ' ')
    foreach ($key in @($start.EnvironmentVariables.Keys)) {
        if ($key -like 'PG*' -or $key -in @('DATABASE_URL', 'TEST_DATABASE_URL', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'ANTHROPIC_API_KEY')) {
            $start.EnvironmentVariables.Remove($key)
        }
    }
    $pointer = [IntPtr]::Zero
    $process = $null
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Credential.Password)
        $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $start.EnvironmentVariables['TEST_DATABASE_URL'] = 'postgresql+psycopg://postgres:' + [uri]::EscapeDataString($password) + '@127.0.0.1:5432/postgres'
        $password = $null
        $process = [Diagnostics.Process]::Start($start)
        $start.EnvironmentVariables.Remove('TEST_DATABASE_URL')
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $pointer = [IntPtr]::Zero
        $stderr = $process.StandardError.ReadToEndAsync()
        while ($null -ne ($line = $process.StandardOutput.ReadLine())) {
            Write-Host $line
        }
        $process.WaitForExit()
        if ($stderr.GetAwaiter().GetResult().Length -gt 0) {
            Write-Host 'Test helper reported a startup/runtime error; details suppressed to protect credentials.'
        }
        return $process.ExitCode
    } finally {
        $password = $null
        $start.EnvironmentVariables.Remove('TEST_DATABASE_URL')
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        if ($null -ne $process) { $process.Dispose() }
    }
}

function Invoke-PostgresTests([string]$Action, [string[]]$Paths) {
    $directory = Get-CredentialDirectory
    $file = Join-Path $directory 'credential.clixml'
    if ($Action -eq 'delete') {
        if (Test-Path -LiteralPath $file) {
            Assert-NoReparsePoint $directory
            Assert-NoReparsePoint $file
            Remove-Item -LiteralPath $file -Force
        }
        Write-Host 'Local encrypted test credential deleted (if present).'
        return 0
    }
    if ($Action -in @('setup', 'rotate')) {
        if ($Action -eq 'setup' -and (Test-Path -LiteralPath $file)) {
            throw 'Credential already exists; use validate or rotate.'
        }
        if (-not (Test-Path -LiteralPath $directory)) {
            New-Item -ItemType Directory -Path $directory -Force | Out-Null
        }
        Assert-NoReparsePoint $directory
        Set-PrivateAcl $directory $true
        $secure = Read-Host 'Local PostgreSQL postgres password (127.0.0.1:5432/postgres)' -AsSecureString
        $credential = New-Object Management.Automation.PSCredential('postgres', $secure)
        try {
            $code = Invoke-CredentialProcess $credential 'validate' @()
            if ($code -ne 0) { return $code }
            $temporary = Join-Path $directory ([guid]::NewGuid().ToString('N') + '.clixml')
            try {
                $credential | Export-Clixml -LiteralPath $temporary
                Set-PrivateAcl $temporary $false
                Assert-PrivateAcl $temporary
                if (Test-Path -LiteralPath $file) {
                    Assert-NoReparsePoint $file
                    [IO.File]::Replace($temporary, $file, [NullString]::Value)
                } else {
                    [IO.File]::Move($temporary, $file)
                }
                Set-PrivateAcl $file $false
                Write-Host 'Encrypted credential saved for this Windows account and computer.'
            } finally {
                if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
            }
        } finally {
            $credential = $null
            $secure.Dispose()
        }
        return 0
    }
    if (-not (Test-Path -LiteralPath $file)) { throw 'Credential missing; run setup in an interactive PowerShell terminal.' }
    Assert-PrivateAcl $directory
    Assert-PrivateAcl $file
    $credential = Import-Clixml -LiteralPath $file
    try {
        return (Invoke-CredentialProcess $credential $Action $Paths)
    } finally {
        if ($credential -is [Management.Automation.PSCredential]) { $credential.Password.Dispose() }
        $credential = $null
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        exit (Invoke-PostgresTests $Command $TestPath)
    } catch {
        # Never render exception objects: native/DPAPI/process errors may contain secrets.
        Write-Host 'PostgreSQL test tooling failed. Check local credential presence/permissions, virtual environment and server; use setup or rotate if needed.'
        exit 1
    }
}
