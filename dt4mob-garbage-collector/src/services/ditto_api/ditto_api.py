import asyncio
import logging
import httpx
from datetime import datetime
from websockets.asyncio.client import connect as ws_connect
from src.models.ditto import SearchResponse, DittoProtocolEnvelope
import json
from src.settings import settings

SEARCH_SIZE = 200

class DittoConnectionError(Exception):
    """Exeption for websocket error"""
    pass

class DittoClient:
    def __init__(self):
        self.uri_ws = settings.ditto.get_base_ws()
        self.uri = settings.ditto.get_base_url()
        
        self.auth_headers = {
            "x-ditto-pre-authenticated": settings.ditto.get_auth()
        }
        logging.debug(f"header:{self.auth_headers}")
        self._ws = None
        self._client = None
        self._responses = {}

    async def connect(self):
        self._ws = await ws_connect(self.uri_ws,additional_headers=self.auth_headers)
        logging.info(f"Conectado ao Ditto em {self.uri}")
        self._client = httpx.Client(
            base_url=settings.ditto.get_base_url(),
            headers=self.auth_headers,
            verify=False,
        )
        asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        if not self._ws:
            raise DittoConnectionError("No Websocket")
        async for message in self._ws:
            data = json.loads(message)
            corr_id = data.get("headers", {}).get("correlation-id")
            
            # Se alguém estiver à espera desta resposta, entrega-a
            logging.debug(f"message: {data}")
            if corr_id in self._responses:
                self._responses[corr_id].set_result(data)
                del self._responses[corr_id]
            else:
                logging.debug(f"Evento não solicitado recebido: {data.get('topic')}")
    
    async def send_ws_message(self, message:DittoProtocolEnvelope) -> bool:
        if not self._ws:
            raise DittoConnectionError("Websocket is None")

        future = asyncio.get_running_loop().create_future()
        cor_id = message.headers.correlation_id
        self._responses[cor_id] = future

        await self._ws.send(message.model_dump_json(by_alias=True,exclude_none=True))

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
        
        return False

    async def close(self):
        if self._client:
            self._client.close()
        if self._ws:
            await self._ws.close()

    def get_all_things_expired_lt(self,time:datetime) -> list[str]:
        if not self._client:
            raise DittoConnectionError("No HTTP client")
        ids: list[str] = []
        query = '/search/things'
        logging.debug(f"time: {time.isoformat()}")
        params = {"fields": "thingId",
                  "filter": f"lt(attributes/expiry_ts,'{time.isoformat()}')",
                  "option": f"size({SEARCH_SIZE})"}
        current_cursor = None
        while True:
            if current_cursor:
                params["option"] = f"size({SEARCH_SIZE}),cursor({current_cursor})"
            resp = self._client.get(url=query,params=params)

            raw_data = resp.json()
            logging.debug(f"Data: {raw_data}")
            data: SearchResponse = SearchResponse(**raw_data)
            if data.items:
                ids.extend([thing["thingId"] for thing in data.items])
            
            if not data.cursor:
                break

            current_cursor = data.cursor
        
        
        return ids
