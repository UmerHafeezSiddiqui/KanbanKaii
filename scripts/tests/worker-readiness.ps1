$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../start-local-server.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $source), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$function = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Wait-ForWorker'}, $true)
Invoke-Expression $function.Extent.Text
$BackendRoot = $PSScriptRoot
$Python = 'Invoke-HeartbeatProbe'
$script:checks = 0
$script:readyAfter = 2
function Invoke-HeartbeatProbe {
    $script:checks++
    Set-Variable -Scope 1 -Name LASTEXITCODE -Value $(if ($script:checks -ge $script:readyAfter) { 0 } else { 1 })
}
function Start-Sleep { param($Seconds) }
$original = Get-Location
Wait-ForWorker -Attempts 3
if ($script:checks -ne 2) { throw 'Readiness did not wait for a successful heartbeat' }
$script:checks = 0
$script:readyAfter = 99
$failed = $false
try { Wait-ForWorker -Attempts 2 } catch { $failed = $_.Exception.Message -like '*no live heartbeat*' }
if (-not $failed -or $script:checks -ne 2) { throw 'An absent worker was reported ready' }
if ((Get-Location).Path -ne $original.Path) { throw 'Readiness did not restore the working directory' }
Write-Host 'Worker readiness regressions passed.'

# ARQ logs success to stderr; exercise a real native process rather than a mock.
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$nativeRoot = Join-Path $project ('.runtime/worker-readiness-test-' + [guid]::NewGuid().ToString('N'))
$Python = Join-Path $project '.runtime/audit-venv/Scripts/python.exe'
if (-not (Test-Path $Python)) { $Python = (Get-Command python -ErrorAction Stop).Source }
New-Item -ItemType Directory -Force (Join-Path $nativeRoot 'arq') | Out-Null
Set-Content (Join-Path $nativeRoot 'arq/__init__.py') ''
$BackendRoot = $nativeRoot
try {
    @'
import sys
sys.stderr.write('Health check successful\n')
sys.exit(0)
'@ | Set-Content (Join-Path $nativeRoot 'arq/__main__.py')
    Wait-ForWorker -Attempts 1
    if ($ErrorActionPreference -ne 'Stop') { throw 'Heartbeat probe changed caller error handling' }
    @'
import sys
sys.stderr.write('Fixture worker has no heartbeat\n')
sys.exit(1)
'@ | Set-Content (Join-Path $nativeRoot 'arq/__main__.py')
    $failed = $false
    try { Wait-ForWorker -Attempts 1 } catch {
        $failed = $_.Exception.Message -like '*Fixture worker has no heartbeat*'
    }
    if (-not $failed) { throw 'Nonzero native exit was ignored or its diagnostics were lost' }
}
finally {
    $resolvedTestRoot = (Resolve-Path $nativeRoot).Path
    if (-not $resolvedTestRoot.StartsWith((Join-Path $project '.runtime') + [IO.Path]::DirectorySeparatorChar)) {
        throw 'Refusing cleanup outside the test workspace'
    }
    Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
}
Write-Host 'Native stderr/exit-code regressions passed.'

