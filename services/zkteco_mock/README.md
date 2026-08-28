# ZKTeco mock API

This service simulates a network attendance device for integration testing. It creates a deterministic SQLite database for July 2026 containing one Casablanca device, the nine employees used by the Odoo demo, and a realistic month of check-in/check-out punches.

The seed excludes weekends and the Moroccan Throne Day on July 30. It also includes approved absence scenarios, several late arrivals and early departures, and one intentional missing checkout (`device_user_id=1007`, July 22) so error handling can be tested.

## Start

```powershell
docker compose up -d zkteco-mock
```

Set a private API key before starting the service:

```powershell
$env:ZKTECO_API_KEY = Read-Host "ZKTeco API key"
```

## API

Health does not require authentication:

```powershell
Invoke-RestMethod http://localhost:8090/health
```

Open the browser-friendly local data viewer directly at [http://localhost:8090/demo](http://localhost:8090/demo). It is intentionally limited to this simulated local service; the programmatic API below remains protected by an API key.

All `/api/v1` routes require the `X-API-Key` header:

```powershell
$headers = @{ "X-API-Key" = $env:ZKTECO_API_KEY }
Invoke-RestMethod http://localhost:8090/api/v1/stats -Headers $headers
Invoke-RestMethod http://localhost:8090/api/v1/devices -Headers $headers
Invoke-RestMethod http://localhost:8090/api/v1/employees -Headers $headers
Invoke-RestMethod "http://localhost:8090/api/v1/punches?after_id=0&limit=100" -Headers $headers
```

Punches support incremental cursor synchronization and optional filters:

- `after_id`: return records whose ID is greater than this cursor.
- `limit`: 1 to 500 records; default 100.
- `from`: inclusive UTC ISO timestamp.
- `to`: exclusive UTC ISO timestamp.
- `device_user_id`: filter one employee.

Continue requesting with the returned `next_after_id` while `has_more` is true. Each punch contains a stable `external_uid`, which should be used for duplicate protection in Odoo.

## Configuration

The service supports these environment variables:

- `ZKTECO_API_KEY`
- `ZKTECO_SEED_MONTH`
- `ZKTECO_DB_PATH`
- `ZKTECO_HOST`
- `ZKTECO_PORT`

Changing the seed month automatically regenerates the persisted mock database. The special Moroccan holiday and attendance exceptions are defined for the default July 2026 dataset.

## Tests

The tests require only Python's standard library:

```powershell
python -m unittest discover services/zkteco_mock/tests -v
```
