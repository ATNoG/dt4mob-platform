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
REQUEST_TIMEOUT_SECONDS = float(env("REQUEST_TIMEOUT_SECONDS", "30"))

USERNAME = read_secret("USERNAME", "USERNAME_FILE")
PASSWORD = read_secret("PASSWORD", "PASSWORD_FILE")


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


def publish_alert_alarm_update(cell: dict[str, Any], *, alert: bool, alarm: bool,) -> None:
    pass


def publish_alert_update(cell: dict[str, Any], *, alert: bool) -> None:
    pass


def publish_alarm_update(cell: dict[str, Any], *, alarm: bool) -> None:
    pass


def process_cell(token: str, cell: dict[str, Any]) -> None:
    value = get_latest_value(token, cell)

    if value is None:
        print(f"[{cell['name']}] No value retrieved, skipping.")
    elif value <= int(cell["alarm_threshold"]):
        print(f"[{cell['name']}] ALARM: value {value} kN <= {cell['alarm_threshold']} kN")
        # TODO: Publish through Hono to update the Ditto thing attributes:
        # alert = True
        # alarm = True
        publish_alert_alarm_update(cell, alert=True, alarm=True)
    elif value <= int(cell["alert_threshold"]):
        print(f"[{cell['name']}] ALERT: value {value} kN <= {cell['alert_threshold']} kN")
        # TODO: Publish through Hono to update the Ditto thing attributes:
        # alert = True
        # alarm = False
        publish_alert_alarm_update(cell, alert=True, alarm=False)
    else:
        print(
            f"[{cell['name']}] Normal: value {value} kN is above threshold "
            f"{cell['alert_threshold']} kN."
        )
        # TODO: Publish through Hono to update the Ditto thing attributes:
        # alert = False
        # alarm = False
        publish_alert_alarm_update(cell, alert=False, alarm=False)
    print("--------------------------------------------------")


if __name__ == "__main__":
    access_token = get_token()
    for load_cell in load_cells():
        try:
            process_cell(access_token, load_cell)
        except Exception as exc:
            print(f"[{load_cell.get('name', 'unknown')}] Failed to process cell: {exc}")
