import asyncio, random
from unittest import mock
from aiohttp import streams

async def run_one(rng):
    sep = bytes(rng.choice(b"ab") for _ in range(rng.randint(1, 4)))
    data = bytes(rng.choice(b"abc") for _ in range(rng.randint(0, 20)))
    cuts = sorted(rng.sample(range(1, len(data)), min(len(data) - 1, rng.randint(0, 6)))) if len(data) > 1 else []
    parts = [data[i:j] for i, j in zip([0] + cuts, cuts + [len(data)])]
    parts = [p for p in parts if p]
    stream = streams.StreamReader(mock.Mock(_reading_paused=False), 2**16, loop=asyncio.get_running_loop())
    delayed = rng.random() < 0.5
    got = []
    async def reader():
        while True:
            line = await stream.readuntil(sep)
            if not line:
                return
            got.append(line)
    if delayed:
        t = asyncio.create_task(reader())
        for p in parts:
            for _ in range(rng.randint(0, 3)):
                await asyncio.sleep(0)
            stream.feed_data(p)
        stream.feed_eof()
        await asyncio.wait_for(t, 1)
    else:
        for p in parts:
            stream.feed_data(p)
        stream.feed_eof()
        await reader()
    exp, pos = [], 0
    while pos < len(data):
        i = data.find(sep, pos)
        end = len(data) if i == -1 else i + len(sep)
        exp.append(data[pos:end]); pos = end
    assert got == exp, (sep, parts, delayed, got, exp)

async def main():
    rng = random.Random(1234)
    for _ in range(20000):
        await run_one(rng)
    print("20000 random cases OK (seed 1234)")
asyncio.run(main())
