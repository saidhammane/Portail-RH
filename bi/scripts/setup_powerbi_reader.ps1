param(
    [string]$Database = "portail_rh_powerbi",
    [string]$Container = "odoo-dev-db-1",
    [string]$PasswordFile = "C:\odoo-dev\bi\local\powerbi_reader_password.txt"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $PasswordFile)) {
    throw "Missing local password file: $PasswordFile"
}
$password = (Get-Content -LiteralPath $PasswordFile -Raw).Trim()
if ($password.Length -lt 16) {
    throw "The local Power BI password must contain at least 16 characters."
}
$escapedPassword = $password.Replace("'", "''")
$sql = @"
DO `$role`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'powerbi_reader') THEN
        EXECUTE format('CREATE ROLE powerbi_reader LOGIN PASSWORD %L', '$escapedPassword');
    ELSE
        EXECUTE format('ALTER ROLE powerbi_reader WITH LOGIN PASSWORD %L', '$escapedPassword');
    END IF;
END
`$role`$;
"@
$sql += @"
ALTER ROLE powerbi_reader NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE $Database TO powerbi_reader;
REVOKE ALL ON SCHEMA public FROM powerbi_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM powerbi_reader;
GRANT USAGE ON SCHEMA bi TO powerbi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA bi TO powerbi_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE odoo IN SCHEMA bi
    GRANT SELECT ON TABLES TO powerbi_reader;
"@

$sql | docker exec -i $Container psql -v ON_ERROR_STOP=1 -U odoo -d $Database
if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure powerbi_reader."
}

$verify = @"
SELECT current_user, COUNT(*) AS rows_visible FROM bi.fact_hr_activity;
SELECT has_table_privilege('powerbi_reader','bi.fact_hr_activity','SELECT') AS can_select,
       has_table_privilege('powerbi_reader','bi.fact_hr_activity','INSERT') AS can_insert,
       has_table_privilege('powerbi_reader','public.hr_employee','SELECT') AS can_read_public;
"@
$verify | docker exec -i $Container psql -U odoo -d $Database
Write-Host "powerbi_reader is configured with read-only access to schema bi."
