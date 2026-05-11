import json
import asyncio
import logging
from datetime import datetime

import httpx
from websockets.asyncio.client import connect as ws_connect

from src.models.ditto import SearchResponse, DittoProtocolEnvelope
from src.services.auth import AuthenticationService
from src.settings.ditto import DittoSettings


class DittoConnectionError(Exception):
    """Exeption for websocket error"""

    pass


class DittoClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        auth_service: AuthenticationService,
        ditto_settings: DittoSettings,
    ):
        self._ws = None
        self._client = client
        self._auth_service = auth_service
        self._ditto_settings = ditto_settings

        self._search_things_url = ditto_settings.get_base_url() + "/search/things"
        self._responses = {}

    async def _get_auth_header(self) -> str:
        token = await self._auth_service.get_token()
        return f"Bearer {token}"

    async def connect(self):
        uri = self._ditto_settings.get_base_ws()
        auth_header = await self._get_auth_header()
        self._ws = await ws_connect(
            uri, additional_headers={"Authorization": auth_header}
        )
        logging.info(f"Connected to ditto at {uri}")
        asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        if self._ws is None:
            raise DittoConnectionError("No Websocket")

        async for message in self._ws:
            data = json.loads(message)
            corr_id = data.get("headers", {}).get("correlation-id")

            # If anyone is waiting for the message it, then deliver it
            logging.debug(f"message: {data}")
            if corr_id in self._responses:
                self._responses[corr_id].set_result(data)
                del self._responses[corr_id]
            else:
                logging.debug(f"Unsolicited event received: {data.get('topic')}")

    async def send_ws_message(self, message: DittoProtocolEnvelope) -> bool:
        if not self._ws:
            raise DittoConnectionError("Websocket is None")

        future = asyncio.get_running_loop().create_future()
        cor_id = message.headers.correlation_id
        self._responses[cor_id] = future

        await self._ws.send(message.model_dump_json(by_alias=True, exclude_none=True))

        try:
            response = await asyncio.wait_for(future, timeout=10.0)
            # O Ditto devolve status nos headers
            status = response.get("headers", {}).get("status")
            return status in [200, 204]
        except asyncio.TimeoutError:
            logging.error(f"Timeout deleting thing {message.topic}")
            return False
        finally:
            self._responses.pop(cor_id, None)

    async def close(self):
        if self._ws is not None:
            await self._ws.close()

    async def get_all_things_expired_lt(self, time: datetime) -> list[str]:
        ids: list[str] = []

        timestamp = time.isoformat()
        logging.debug(f"time: {timestamp}")
        filter_option = f"size({self._ditto_settings.search_size})"
        params = {
            "fields": "thingId",
            "filter": f"lt(attributes/expiry_ts,'{timestamp}')",
            "option": filter_option,
        }

        current_cursor = None
        while True:
            if current_cursor is not None:
                params["option"] = f"{filter_option},cursor({current_cursor})"

            auth_header = await self._get_auth_header()
            resp = await self._client.get(
                url=self._search_things_url,
                params=params,
                headers={"Authorization": auth_header},
            )
            logging.debug(f"Data: {resp.content}")

            data: SearchResponse = SearchResponse.model_validate_json(resp.content)
            if data.items is not None:
                ids.extend([thing["thingId"] for thing in data.items])

            if data.cursor is None:
                break

            current_cursor = data.cursor

        return ids
