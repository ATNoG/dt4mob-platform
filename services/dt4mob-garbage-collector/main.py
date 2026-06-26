from src.services.garbage_collector import garbage_collector
from src.services.ditto_api import ditto_client

import logging
import asyncio


async def main():
    await ditto_client.connect()

    envelops = await garbage_collector.get_expired_envelops()

    while len(envelops) > 5:
        logging.info(f"number things:{len(envelops)}")
        for envelop in envelops:
            try:
                await ditto_client.send_ws_message(envelop)

            except Exception as e:
                logging.error(f"Failed to process {envelop.topic}: {type(e).__name__}: {e}")
                continue
        envelops = await garbage_collector.get_expired_envelops()

    logging.info("Done, closing client and mqtt")
    await ditto_client.close()


if __name__ == "__main__":
    asyncio.run(main())
