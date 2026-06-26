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
    
    async def _token_refresh_loop(self):
        """Background task that maintains the WebSocket authorization state."""
        logging.info("Starting background WebSocket token lifecycle supervisor.")
        try:
            while self._ws is not None:
                time_left = self._auth_service.seconds_until_expiration()
                
                sleep_interval = max(5.0, time_left - 5.0) 
                
                logging.debug(f"Token has {time_left:.1f}s left. Supervisor sleeping for {sleep_interval:.1f}s")
                await asyncio.sleep(sleep_interval)
                
                if self._ws is None:
                    break

                logging.info("Token buffer threshold met. Requesting upstream identity update...")
                fresh_token = await self._auth_service.refresh()
                
                control_payload = f"JWT-TOKEN?jwtToken={fresh_token}"
                
                logging.debug("Sending token extension frame control message payload to Ditto.")
                await self._ws.send(control_payload)
                logging.info("WebSocket authorization extension lease pushed successfully.")
                
        except asyncio.CancelledError:
            logging.debug("Token supervisor loop task cleanly cancelled.")
        except Exception as e:
            logging.error(f"Error encountered in token lifetime supervisor: {e}", exc_info=True)
        
    async def send_control_message(self, command: str, timeout: float = 20.0) -> bool:
        """
        Sends a plaintext control command (e.g., START-SEND-EVENTS) to Eclipse Ditto 
        and waits for its corresponding string ACK.
        """
        if not self._ws:
            raise DittoConnectionError("Websocket is not connected")

        base_command = command.split('?')[0]
        expected_ack = f"{base_command}:ACK"

        ack_future = asyncio.get_running_loop().create_future()
        
        self._responses[expected_ack] = ack_future

        try:
            logging.debug(f"Sending Ditto control command: {command}")
            await self._ws.send(command)
            
            await asyncio.wait_for(ack_future, timeout=timeout)
            logging.info(f"Successfully subscribed via control command: {base_command}")
            return True

        except asyncio.TimeoutError:
            logging.error(f"Timeout waiting for control ACK: {expected_ack}")
            return False
        finally:
            self._responses.pop(expected_ack, None)

    async def connect(self):
        uri = self._ditto_settings.get_base_ws()
        auth_header = await self._get_auth_header()
        self._ws = await ws_connect(
            uri, additional_headers={"Authorization": auth_header}
        )
        logging.info(f"Connected to ditto at {uri}")
        asyncio.create_task(self._listen_loop())
        self._refresh_task = asyncio.create_task(self._token_refresh_loop())

    async def _listen_loop(self):
        if self._ws is None:
            raise DittoConnectionError("No Websocket")

        async for message in self._ws:

            if isinstance(message, str) and message.endswith(":ACK"):
                    future = self._responses.pop(message, None)
                    if future and not future.done():
                        future.set_result(True)
                    continue

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
            logging.info(f"response:{response}")
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

    async def get_things_expired_lt(self, time: datetime, limit: int = 500) -> list[str]:
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
        while True and len(ids) < limit:
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
