param(
    [string]$Database = "portail_rh_powerbi",
    [string]$Container = "odoo-dev-db-1"
)

$ErrorActionPreference = "Stop"
$biRoot = Split-Path $PSScriptRoot -Parent
$sqlFile = Join-Path $biRoot "sql\powerbi_reporting_views.sql"

Write-Host "Deploying PostgreSQL reporting views to $Database..."
$containerSql = "/tmp/powerbi_reporting_views.sql"
docker cp $sqlFile "${Container}:$containerSql" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Unable to copy reporting SQL." }
docker exec -i $Container psql -v ON_ERROR_STOP=1 -U odoo -d $Database -f $containerSql
if ($LASTEXITCODE -ne 0) { throw "Reporting view deployment failed." }
docker exec $Container rm -f $containerSql | Out-Null

& (Join-Path $PSScriptRoot "setup_powerbi_reader.ps1") -Database $Database -Container $Container

$views = @(
    "dim_company", "dim_department", "dim_employee", "fact_hr_activity",
    "fact_travel_request", "fact_supply_request", "fact_attestation_request",
    "fact_attendance", "fact_zkteco_log", "fact_onboarding_message",
    "fact_onboarding_document"
)
foreach ($view in $views) {
    $count = docker exec $Container psql -U powerbi_reader -d $Database -Atc "SELECT count(*) FROM bi.$view;"
    if ($LASTEXITCODE -ne 0) { throw "Read-only validation failed for bi.$view." }
    Write-Host ("{0,-32} {1,8} rows" -f "bi.$view", $count)
}
Write-Host "Direct PostgreSQL BI layer is ready. No CSV or Excel staging is used."