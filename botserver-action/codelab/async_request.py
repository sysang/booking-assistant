import asyncio
import requests
import time

def make_request(i, z):
    time.sleep(1)
    return z

async def main():
    loop = asyncio.get_running_loop()
    futures = [loop.run_in_executor( None, make_request, i, i*10) for i in range(50)]

    result = []
    for response in await asyncio.gather(*futures):
        result.append(response)

    return result


result = asyncio.run(main())
print(result)
