import sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path('repos/validation-2026-09-27/nonlinux/aiohttp').resolve()))
import aiohttp
from aiohttp.streams import StreamReader
from aiohttp.base_protocol import BaseProtocol
async def main():
 print('actual source',aiohttp.__file__)
 for parts in [(b'abc\r\nrest',),(b'abc\r',b'\nrest')]:
  r=StreamReader(BaseProtocol(asyncio.get_running_loop()),limit=1024,loop=asyncio.get_running_loop())
  for p in parts:r.feed_data(p)
  r.feed_eof()
  got=await r.readuntil(b'\r\n');tail=await r.read()
  print('chunks',repr(parts),'readuntil',repr(got),'remainder',repr(tail))
  if len(parts)==1:assert got==b'abc\r\n' and tail==b'rest'
  else:assert got==b'abc\r\nrest' and tail==b''
 print('CONFIRMED: same byte stream changes result with feed_data boundaries')
asyncio.run(main())
