# Grafana Alert Provisioner

Provision and manage Grafana alert rules programmatically from JSON files.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables or create a `.env` file:

```bash
# Required
GRAFANA_URL=https://your-grafana-instance.com

# Authentication (choose one)
GRAFANA_TOKEN=glsa_xxxxxxxxxxxx        # Service account token (recommended)
# OR
GRAFANA_USER=admin                      # Basic auth
GRAFANA_PASSWORD=secret
```

### Creating a Service Account Token

1. Go to Grafana → Administration → Service Accounts
2. Create a new service account
3. Assign "Editor" or "Admin" role
4. Click "Add token" and copy it to `GRAFANA_TOKEN`

> **Note:** API keys were deprecated in Grafana 12.3 (Jan 2025). Use Service Account Tokens instead.

## Usage

### Import Alert Rules

```bash
# Single file
python scripts/add-alert.py alerts/cpu-alert.json

# Multiple files
python scripts/add-alert.py alerts/*.json

# Dry run (validate only)
python scripts/add-alert.py --dry-run alerts/*.json
```

### Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Validate JSON files without importing |
| `--folder` | Override folder UID for all alerts |

## Alert JSON Format

Alert definitions follow the [Grafana Alerting API](https://grafana.com/docs/grafana/latest/developers/http_api/alerting_provisioning/) format:

```json
{
  "title": "High CPU Usage",
  "ruleGroup": "system-alerts",
  "folderUID": "system-monitoring",
  "condition": "C",
  "noDataState": "NoData",
  "execErrState": "Error",
  "for": "5m",
  "annotations": {
    "summary": "CPU usage is above 80%"
  },
  "labels": {
    "severity": "warning"
  },
  "data": [
    {
      "refId": "A",
      "datasourceUid": "prometheus",
      "model": {
        "expr": "your_prometheus_query"
      }
    }
  ]
}
```

See `examples/` for complete alert definitions.

## Docker

```bash
# Build
docker build -t grafana-alert-provisioner .

# Run
docker run -e GRAFANA_URL=https://... -e GRAFANA_TOKEN=... \
  -v $(pwd)/alerts:/app/alerts \
  grafana-alert-provisioner scripts/add-alert.py /app/alerts/my-alert.json
```

## Examples

### CPU Alert
```bash
python scripts/add-alert.py examples/cpu-alert.json
```

### Bulk Import
```bash
# Export from source Grafana, import to target
python scripts/add-alert.py exported-alerts/*.json
```

## License

MIT
