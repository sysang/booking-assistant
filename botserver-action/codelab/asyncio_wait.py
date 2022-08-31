import asyncio
import time

fast_result = None
long_result = None

async def fast():
    global fast_result
    await asyncio.sleep(1)
    fast_result = 'fast -> done'
    return 1

async def long():
    global long_result
    await asyncio.sleep(5)
    long_result = 'long -> done'
    return 5

async def main():
    corofast = asyncio.create_task(fast())
    corolong = asyncio.create_task(long())
    print('fast_result: ', fast_result)
    print('long_result: ', long_result)

    done, pending = await asyncio.wait({corofast, corolong}, return_when=asyncio.FIRST_COMPLETED)

    time.sleep(6)

    if corofast in done:
        print(corofast)

    print(fast_result)
    print(long_result)

asyncio.run(main())
