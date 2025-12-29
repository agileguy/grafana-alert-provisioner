#!/usr/bin/env python3
"""
remove-alert.py - Remove Grafana alert rules by name or UID

Usage:
    python remove-alert.py <alert-name-or-uid>
    python remove-alert.py --uid <alert-uid>
    python remove-alert.py --name "High CPU Usage"

Environment Variables:
    GRAFANA_URL      - Grafana server URL (e.g., https://grafana.example.com)
    GRAFANA_TOKEN    - Service account token with alerting permissions
    GRAFANA_USER     - (Optional) Basic auth username
    GRAFANA_PASSWORD - (Optional) Basic auth password

Example:
    export GRAFANA_URL=https://grafana.example.com
    export GRAFANA_TOKEN=glsa_xxxxxxxxxxxx
    python remove-alert.py "High CPU Usage"
    python remove-alert.py --uid ef8iwvb3m0feoc
"""

import argparse
import os
import sys
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


def list_alerts(config: dict) -> list:
    """List all provisioned alert rules."""
    url = f"{config['url']}/api/v1/provisioning/alert-rules"

    response = requests.get(
        url,
        headers=get_headers(config),
        auth=get_auth(config),
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def find_alert_by_name(config: dict, name: str) -> Optional[dict]:
    """Find an alert rule by its title."""
    alerts = list_alerts(config)

    for alert in alerts:
        if alert.get("title") == name:
            return alert

    return None


def get_alert_by_uid(config: dict, uid: str) -> Optional[dict]:
    """Get an alert rule by UID."""
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


def delete_alert(config: dict, uid: str) -> bool:
    """Delete an alert rule by UID."""
    url = f"{config['url']}/api/v1/provisioning/alert-rules/{uid}"

    response = requests.delete(
        url,
        headers=get_headers(config),
        auth=get_auth(config),
        timeout=30,
    )

    response.raise_for_status()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Remove Grafana alert rules by name or UID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "identifier",
        nargs="?",
        help="Alert name or UID to remove",
    )
    parser.add_argument(
        "--uid",
        type=str,
        help="Remove alert by UID",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Remove alert by name/title",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_alerts",
        help="List all alert rules",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    config = load_config()

    print(f"Grafana URL: {config['url']}")
    print(f"Auth: {'Service Account Token' if config['token'] else 'Basic Auth'}")
    print()

    # List mode
    if args.list_alerts:
        try:
            alerts = list_alerts(config)
            if not alerts:
                print("No alert rules found.")
                return

            print(f"Found {len(alerts)} alert rule(s):\n")
            for alert in alerts:
                print(f"  Title: {alert.get('title', 'N/A')}")
                print(f"  UID:   {alert.get('uid', 'N/A')}")
                print(f"  Group: {alert.get('ruleGroup', 'N/A')}")
                print()
        except requests.HTTPError as e:
            print(f"Error listing alerts: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            sys.exit(1)
        return

    # Determine what to delete
    uid_to_delete = None
    alert_info = None

    if args.uid:
        uid_to_delete = args.uid
        alert_info = get_alert_by_uid(config, args.uid)
        if not alert_info:
            print(f"Error: No alert found with UID '{args.uid}'", file=sys.stderr)
            sys.exit(1)
    elif args.name:
        alert_info = find_alert_by_name(config, args.name)
        if not alert_info:
            print(f"Error: No alert found with name '{args.name}'", file=sys.stderr)
            sys.exit(1)
        uid_to_delete = alert_info.get("uid")
    elif args.identifier:
        # Try UID first, then name
        alert_info = get_alert_by_uid(config, args.identifier)
        if alert_info:
            uid_to_delete = args.identifier
        else:
            alert_info = find_alert_by_name(config, args.identifier)
            if alert_info:
                uid_to_delete = alert_info.get("uid")
            else:
                print(f"Error: No alert found with name or UID '{args.identifier}'", file=sys.stderr)
                sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    # Show what will be deleted
    title = alert_info.get("title", "Unknown")
    print(f"Alert to remove:")
    print(f"  Title: {title}")
    print(f"  UID:   {uid_to_delete}")
    print(f"  Group: {alert_info.get('ruleGroup', 'N/A')}")
    print()

    if args.dry_run:
        print("DRY RUN - No changes made")
        return

    # Confirm deletion
    if not args.force:
        confirm = input("Are you sure you want to delete this alert? [y/N] ")
        if confirm.lower() not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    # Delete the alert
    try:
        delete_alert(config, uid_to_delete)
        print(f"✓ Deleted: {title} (UID: {uid_to_delete})")
    except requests.HTTPError as e:
        print(f"Error deleting alert: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error deleting alert: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
