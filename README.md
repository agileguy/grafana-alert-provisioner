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

Supports two JSON formats:
1. **Simple format** - Individual alert rules
2. **Export format** - Grafana export with `apiVersion`, `groups`, and nested `rules`

```bash
# Single file (simple format)
python scripts/add-alert.py alerts/cpu-alert.json

# Grafana export format (auto-detected)
python scripts/add-alert.py exported-alerts.json

# Multiple files
python scripts/add-alert.py alerts/*.json

# Dry run (validate only)
python scripts/add-alert.py --dry-run alerts/*.json

# Override folder for all alerts
python scripts/add-alert.py --folder my-folder-uid alerts/*.json
```

#### Add Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Validate JSON files without importing |
| `--folder` | Override folder UID for all alerts |

#### Supported Formats

**Simple format** (single alert):
```json
{
  "title": "My Alert",
  "folderUID": "alerts",
  "condition": "C",
  "data": [...]
}
```

**Export format** (from Grafana UI export):
```json
{
  "apiVersion": 1,
  "groups": [
    {
      "name": "my-group",
      "folder": "MyFolder",
      "rules": [...]
    }
  ]
}
```

The export format automatically maps folder names to UIDs.

### Remove Alert Rules

```bash
# By name
python scripts/remove-alert.py "High CPU Usage"

# By UID
python scripts/remove-alert.py --uid ef8iwvb3m0feoc

# List all alerts
python scripts/remove-alert.py --list

# Dry run (show what would be deleted)
python scripts/remove-alert.py --dry-run "High CPU Usage"

# Skip confirmation prompt
python scripts/remove-alert.py -f "High CPU Usage"
```

#### Remove Options

| Flag | Description |
|------|-------------|
| `--uid` | Remove alert by UID |
| `--name` | Remove alert by name/title |
| `--list` | List all alert rules |
| `--dry-run` | Show what would be deleted without deleting |
| `-f, --force` | Skip confirmation prompt |

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
