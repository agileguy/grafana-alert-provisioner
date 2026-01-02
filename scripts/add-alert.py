#!/usr/bin/env python3
"""
add-alert.py - Import Grafana alert rules from JSON file

Supports two formats:
  1. Individual alert rules (simple format)
  2. Grafana export format (with apiVersion, groups, and nested rules)

Usage:
    python add-alert.py <alert-definition.json>
    python add-alert.py alerts/*.json
    python add-alert.py exported-alerts.json  # Grafana export format

Environment Variables:
    GRAFANA_URL      - Grafana server URL (e.g., https://grafana.example.com)
    GRAFANA_TOKEN    - Service account token with alerting permissions
    GRAFANA_USER     - (Optional) Basic auth username
    GRAFANA_PASSWORD - (Optional) Basic auth password

Example:
    export GRAFANA_URL=https://grafana.example.com
    export GRAFANA_TOKEN=glsa_xxxxxxxxxxxx
    python add-alert.py my-alert.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv


def load_config() -> dict:
    """Load configuration from environment variables."""
    load_dotenv()

    config = {
        "url": os.getenv("GRAFANA_URL"),
        "token": os.getenv("GRAFANA_TOKEN"),
        "user": os.getenv("GRAFANA_USER"),
        "password": os.getenv("GRAFANA_PASSWORD"),
    }

    if not config["url"]:
        print("Error: GRAFANA_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    # Remove trailing slash
    config["url"] = config["url"].rstrip("/")

    if not config["token"] and not (config["user"] and config["password"]):
        print("Error: Either GRAFANA_TOKEN or GRAFANA_USER/GRAFANA_PASSWORD required", file=sys.stderr)
        sys.exit(1)

    return config


def get_headers(config: dict) -> dict:
    """Build request headers with authentication."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if config["token"]:
        headers["Authorization"] = f"Bearer {config['token']}"

    return headers


def get_auth(config: dict) -> Optional[tuple]:
    """Get basic auth tuple if configured."""
    if config["user"] and config["password"]:
        return (config["user"], config["password"])
    return None


def get_folders(config: dict) -> dict:
    """Get all folders and return a name->uid mapping."""
    url = f"{config['url']}/api/folders"

    try:
        response = requests.get(
            url,
            headers=get_headers(config),
            auth=get_auth(config),
            timeout=30,
        )
        response.raise_for_status()
        folders = response.json()
        return {f["title"]: f["uid"] for f in folders}
    except requests.RequestException:
        return {}


def is_export_format(data: dict) -> bool:
    """Check if JSON is in Grafana export format (has apiVersion and groups)."""
    return "apiVersion" in data and "groups" in data


def extract_rules_from_export(config: dict, data: dict, folder_override: Optional[str] = None) -> list:
    """Extract individual alert rules from Grafana export format."""
    rules = []
    folders = None  # Lazy load

    for group in data.get("groups", []):
        group_name = group.get("name", "default")
        folder_name = group.get("folder", "")

        # Determine folder UID
        folder_uid = folder_override
        if not folder_uid and folder_name:
            # Look up folder UID by name
            if folders is None:
                folders = get_folders(config)
            folder_uid = folders.get(folder_name)
            if not folder_uid:
                print(f"  Warning: Folder '{folder_name}' not found, skipping group '{group_name}'", file=sys.stderr)
                continue

        for rule in group.get("rules", []):
            # Add required fields for API
            rule["ruleGroup"] = group_name
            if folder_uid:
                rule["folderUID"] = folder_uid
            rules.append(rule)

    return rules


def validate_alert_json(data: dict) -> bool:
    """Validate alert rule JSON structure."""
    required_fields = ["title", "condition", "data"]

    for field in required_fields:
        if field not in data:
            print(f"Error: Missing required field '{field}' in alert definition", file=sys.stderr)
            return False

    return True


def get_existing_alert(config: dict, uid: str) -> Optional[dict]:
    """Check if alert rule already exists."""
    url = f"{config['url']}/api/v1/provisioning/alert-rules/{uid}"

    try:
        response = requests.get(
            url,
            headers=get_headers(config),
            auth=get_auth(config),
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()
        return None
    except requests.RequestException:
        return None


def create_alert(config: dict, alert_data: dict) -> dict:
    """Create a new alert rule."""
    url = f"{config['url']}/api/v1/provisioning/alert-rules"

    response = requests.post(
        url,
        headers=get_headers(config),
        auth=get_auth(config),
        json=alert_data,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def update_alert(config: dict, uid: str, alert_data: dict) -> dict:
    """Update an existing alert rule."""
    url = f"{config['url']}/api/v1/provisioning/alert-rules/{uid}"

    response = requests.put(
        url,
        headers=get_headers(config),
        auth=get_auth(config),
        json=alert_data,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def import_alert(config: dict, file_path: Path, folder_override: Optional[str] = None) -> tuple:
    """Import alerts from JSON file. Returns (success_count, total_count)."""
    print(f"Processing: {file_path}")

    try:
        with open(file_path, "r") as f:
            alert_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  Error: Invalid JSON - {e}", file=sys.stderr)
        return (0, 1)
    except FileNotFoundError:
        print(f"  Error: File not found", file=sys.stderr)
        return (0, 1)

    # Detect format and extract alerts
    if isinstance(alert_data, dict) and is_export_format(alert_data):
        print(f"  Detected Grafana export format")
        alerts = extract_rules_from_export(config, alert_data, folder_override)
        if not alerts:
            print(f"  Error: No valid rules found in export", file=sys.stderr)
            return (0, 1)
    elif isinstance(alert_data, list):
        alerts = alert_data
    else:
        alerts = [alert_data]

    # Apply folder override if specified
    if folder_override:
        for alert in alerts:
            alert["folderUID"] = folder_override

    success_count = 0
    for alert in alerts:
        if not validate_alert_json(alert):
            continue

        title = alert.get("title", "Unnamed")
        uid = alert.get("uid")

        try:
            # Check if alert exists (if UID provided)
            if uid and get_existing_alert(config, uid):
                result = update_alert(config, uid, alert)
                print(f"  Updated: {title} (UID: {result.get('uid', 'N/A')})")
            else:
                result = create_alert(config, alert)
                print(f"  Created: {title} (UID: {result.get('uid', 'N/A')})")

            success_count += 1

        except requests.HTTPError as e:
            error_msg = e.response.text if e.response else str(e)
            print(f"  Error importing '{title}': {e.response.status_code} - {error_msg}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  Error importing '{title}': {e}", file=sys.stderr)

    return (success_count, len(alerts))


def main():
    parser = argparse.ArgumentParser(
        description="Import Grafana alert rules from JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="JSON file(s) containing alert definitions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files without importing",
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Override folder UID for all alerts",
    )

    args = parser.parse_args()

    config = load_config()

    print(f"Grafana URL: {config['url']}")
    print(f"Auth: {'Service Account Token' if config['token'] else 'Basic Auth'}")
    print()

    if args.dry_run:
        print("DRY RUN - Validating files only\n")

    total_success = 0
    total_failed = 0

    for file_path in args.files:
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            total_failed += 1
            continue

        if args.dry_run:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                # Handle export format in dry-run
                if isinstance(data, dict) and is_export_format(data):
                    print(f"✓ {file_path} (Grafana export format)")
                    rule_count = sum(len(g.get("rules", [])) for g in data.get("groups", []))
                    print(f"  Contains {len(data.get('groups', []))} group(s), {rule_count} rule(s)")
                    total_success += 1
                else:
                    alerts = data if isinstance(data, list) else [data]
                    valid = all(validate_alert_json(a) for a in alerts)
                    print(f"{'✓' if valid else '✗'} {file_path}")
                    if valid:
                        total_success += 1
                    else:
                        total_failed += 1
            except json.JSONDecodeError as e:
                print(f"✗ {file_path} - Invalid JSON: {e}")
                total_failed += 1
        else:
            success, total = import_alert(config, file_path, args.folder)
            total_success += success
            total_failed += (total - success)

    print()
    print(f"Summary: {total_success} succeeded, {total_failed} failed")

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
