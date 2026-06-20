import json
import os
from typing import Any

import requests


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"{name} must be set")
    return value


def read_secret(name: str, file_name: str) -> str:
    direct_value = os.getenv(name)
    if direct_value:
        return direct_value

    path = os.getenv(file_name)
    if not path:
        raise ValueError(f"One of {name} or {file_name} must be set")

    with open(path, encoding="utf-8") as secret_file:
        return secret_file.read().strip()


KEYCLOAK_URL = env("KEYCLOAK_URL")
KEYCLOAK_CA_CRT_FILE = os.getenv("KEYCLOAK_CA_CRT_FILE")
CLIENT_ID = env("CLIENT_ID", "ditto")
API_URL = env("API_URL").rstrip("/")
SINCE = env("SINCE")
GRAFANA_URL = env("GRAFANA_URL").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(env("REQUEST_TIMEOUT_SECONDS", "30"))

USERNAME = read_secret("USERNAME", "USERNAME_FILE")
PASSWORD = read_secret("PASSWORD", "PASSWORD_FILE")
GRAFANA_TOKEN = read_secret("GRAFANA_TOKEN", "GRAFANA_TOKEN_FILE")


def load_cells() -> list[dict[str, Any]]:
    raw_cells = env("LOAD_CELLS_JSON")
    cells = json.loads(raw_cells)
    if not isinstance(cells, list):
        raise ValueError("LOAD_CELLS_JSON must contain a JSON list")
    return cells


def get_token() -> str:
    response = requests.post(
        KEYCLOAK_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": USERNAME,
            "password": PASSWORD,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
        verify=KEYCLOAK_CA_CRT_FILE or True,
    )
    if not response.ok:
        print(response.status_code)
        print(response.text)
    response.raise_for_status()
    print("Successfully obtained Keycloak token")
    return response.json()["access_token"]


def get_latest_value(token: str, cell: dict[str, Any]) -> int | None:
    response = requests.get(
        f"{API_URL}/{cell['instrument']}",
        headers={"Authorization": f"Bearer {token}"},
        params={"since": SINCE},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    items = [
        value
        for value in data
        if value.get("path") == "/features/F/properties/latestValue"
    ]

    if not items:
        print(f"[{cell['name']}] No matching data found")
        return None

    latest = items[0]
    value = latest["value"]["valor"]
    timestamp = latest["value"]["timestamp"]
    print(f"[{cell['name']}] Date/Time: {timestamp} | Latest value: {value} kN")
    return int(value)


def grafana_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {GRAFANA_TOKEN}",
        "Content-Type": "application/json",
    }


def send_annotation(value: int, cell: dict[str, Any], status: str) -> None:
    if status == "alarm":
        text = (
            f"ALARME Celula de Carga {cell['name']}: {value} kN "
            f"(threshold: {cell['alarm_threshold']} kN)"
        )
    else:
        text = (
            f"ALERTA Celula de Carga {cell['name']}: {value} kN "
            f"(threshold: {cell['alert_threshold']} kN)"
        )

    response = requests.post(
        f"{GRAFANA_URL}/api/annotations",
        headers=grafana_headers(),
        json={"text": text, "tags": cell["tags"]},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.ok:
        print(f"{status.capitalize()} annotation sent to Grafana: {text}")
        return

    print(f"Failed to send {status} annotation: {response.status_code} - {response.text}")


def fetch_annotations(cell: dict[str, Any]) -> list[dict[str, Any]]:
    response = requests.get(
        f"{GRAFANA_URL}/api/annotations",
        headers={"Authorization": f"Bearer {GRAFANA_TOKEN}"},
        params={"tags": cell["tags"], "limit": 100},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if not response.ok:
        print(
            f"[{cell['name']}] Failed to fetch annotations: "
            f"{response.status_code} - {response.text}"
        )
        return []

    return response.json()


def delete_annotation(annotation_id: int, cell: dict[str, Any], reason: str) -> None:
    response = requests.delete(
        f"{GRAFANA_URL}/api/annotations/{annotation_id}",
        headers={"Authorization": f"Bearer {GRAFANA_TOKEN}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.ok:
        print(f"[{cell['name']}] Deleted annotation {annotation_id}, {reason}.")
    else:
        print(
            f"[{cell['name']}] Failed to delete annotation {annotation_id}: "
            f"{response.status_code}"
        )


def delete_all_alert_annotations(cell: dict[str, Any]) -> None:
    for annotation in fetch_annotations(cell):
        delete_annotation(annotation["id"], cell, "as the value is now normal")


def keep_only_latest_annotation(cell: dict[str, Any]) -> None:
    annotations = fetch_annotations(cell)
    if len(annotations) <= 1:
        return

    annotations.sort(key=lambda annotation: annotation["time"], reverse=True)
    for annotation in annotations[1:]:
        delete_annotation(
            annotation["id"],
            cell,
            "to update alert/alarm status",
        )


def process_cell(token: str, cell: dict[str, Any]) -> None:
    value = get_latest_value(token, cell)

    if value is None:
        print(f"[{cell['name']}] No value retrieved, skipping.")
    elif value <= int(cell["alarm_threshold"]):
        print(f"[{cell['name']}] ALARM: value {value} kN <= {cell['alarm_threshold']} kN")
        send_annotation(value, cell, "alarm")
    elif value <= int(cell["alert_threshold"]):
        print(f"[{cell['name']}] ALERT: value {value} kN <= {cell['alert_threshold']} kN")
        send_annotation(value, cell, "alert")
    else:
        print(
            f"[{cell['name']}] Normal: value {value} kN is above threshold "
            f"{cell['alert_threshold']} kN, no annotation sent."
        )
        delete_all_alert_annotations(cell)

    keep_only_latest_annotation(cell)
    print("--------------------------------------------------")


if __name__ == "__main__":
    access_token = get_token()
    for load_cell in load_cells():
        try:
            process_cell(access_token, load_cell)
        except Exception as exc:
            print(f"[{load_cell.get('name', 'unknown')}] Failed to process cell: {exc}")
