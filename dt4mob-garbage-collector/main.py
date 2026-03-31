from src.services.garbage_collector import garbage_collector
from src.services.ditto_api import ditto_client
from src.settings import settings

import logging
import asyncio

BATCH_SIZE = settings.batch_size

async def main():
    await ditto_client.connect()
    
    envelops = garbage_collector.get_expired_envelops()

    
    if not envelops:
        logging.info("No expired Things to Delete.")
        return

    logging.info(f"Found {len(envelops)} expired Things to Delete.")

    for envelop in envelops:
        try:
             await ditto_client.send_ws_message(envelop)

        except Exception as e:
            logging.error(f"Failed to process {envelop.topic}: {type(e).__name__}: {e}")
            continue
    
    logging.info("Done, closing client and mqtt")
    await ditto_client.close()
    

if __name__ == "__main__":
    asyncio.run(main())