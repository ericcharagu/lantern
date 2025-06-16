import valkey
from loguru import logger
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import asyncio
# Valkey client setup (consider making this a singleton)
valkey_client = valkey.Valkey(host='localhost', port=6379, db=0, decode_responses=True)

class ValkeyStoreData(BaseModel):
    request_id: str
    request_status: str

def init_cache(cache_data: ValkeyStoreData) -> Optional[str]:
    """
    Thread-safe function to store and retrieve data from Valkey
    Returns the stored value if successful, None otherwise
    """
    try:
        # Use pipeline for atomic operations
        with valkey_client.pipeline() as pipe:
            pipe.set(cache_data.request_id, cache_data.request_status)
            pipe.get(cache_data.request_id)
            result = pipe.execute()
        return result[1]  # Return the get() result
    except valkey.ValkeyError as e:
        logger.error(f"Valkey operation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None

async def async_init_cache(cache_data: ValkeyStoreData) -> Optional[str]:
    """
    Async version using thread pool executor
    """
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None,  # Uses default executor
            init_cache,
            cache_data
        )
    except Exception as e:
        logger.error(f"Async operation failed: {e}")
        return None
async def async_main():
    # Async example
    test_data = ValkeyStoreData(request_id='async_foo', request_status='async_bar')
    result = await async_init_cache(test_data)
    print(f"Async cache operation result: {result}")

if __name__ == "__main__":
    # Asynchronous execution
    asyncio.run(async_main())
