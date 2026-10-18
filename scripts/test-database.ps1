# Starts only an isolated test Postgres container; never links to a hosted project.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$work = Join-Path $root '.runtime/database-verification'
$schema = Join-Path $work 'supabase'
New-Item -ItemType Directory -Force $schema | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'supabase/migrations') -Destination $schema -Recurse -Force
$config = Get-Content (Join-Path $root 'supabase/config.toml') -Raw
$config = $config.Replace('project_id = "kanbankaii"', 'project_id = "kanbankaii-audit"').Replace('54322', '55432').Replace('54320', '55430')
# SQL regressions do not use Storage; avoid bootstrapping its unrelated service.
$config = [regex]::Replace($config, '(\[storage\]\s*enabled\s*=\s*)true', '${1}false')
Set-Content (Join-Path $schema 'config.toml') $config
try {
    & npx --yes supabase@2.121.0 --workdir $work db start
    if ($LASTEXITCODE -ne 0) { throw 'Local test database startup failed' }
    & npx --yes supabase@2.121.0 --workdir $work db reset --local --no-seed
    if ($LASTEXITCODE -ne 0) { throw 'Local test migration reset failed' }
    foreach ($test in Get-ChildItem (Join-Path $root 'supabase/tests') -Filter '*.sql') {
        Get-Content $test.FullName -Raw | docker exec -i supabase_db_kanbankaii-audit psql -U postgres -d postgres -v ON_ERROR_STOP=1
        if ($LASTEXITCODE -ne 0) { throw "Database regression failed: $($test.Name)" }
    }
}
finally {
    & npx --yes supabase@2.121.0 --workdir $work stop --no-backup
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Test database cleanup failed. Inspect the kanbankaii-audit project after Docker is healthy.'
    }
}
