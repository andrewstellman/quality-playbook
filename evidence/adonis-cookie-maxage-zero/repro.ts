import { createServer } from 'node:http'
import { EncryptionFactory } from '/tmp/adonw/node_modules/@boringnode/encryption/build/factories/main.js'
import { HttpResponseFactory } from '/tmp/adonw/factories/response.ts'
import { serializeCookie } from '/tmp/adonw/src/helpers.ts'

const encryption = new EncryptionFactory().create()
const server = createServer((req, res) => {
  const response = new HttpResponseFactory().merge({ req, res, encryption }).create() // factory config maxAge: 90
  response.cookie('a', 'v', { maxAge: 0 })
  response.plainCookie('b', 'v', { maxAge: 0 })
  response.encryptedCookie('c', 'v', { maxAge: 0 })
  response.plainCookie('d', 'v', { maxAge: 60 }) // control
  response.send('ok'); response.finish()
})
await new Promise<void>((r) => server.listen(0, r))
const port = (server.address() as any).port
const cookies = (await fetch(`http://localhost:${port}/`)).headers.getSetCookie()
server.close()
console.log('serializeCookie(maxAge:0)   :', serializeCookie('s', 'v', { maxAge: 0 }))
try { console.log('serializeCookie(maxAge:"0s"):', serializeCookie('s', 'v', { maxAge: '0s' })) } catch (e: any) { console.log('serializeCookie(maxAge:"0s"): throws', e.message) }
for (const c of cookies) console.log('Set-Cookie:', c.replace(/=[^;]{20,}/, '=<value>'))
const bad = cookies.slice(0, 3).filter((c) => !/Max-Age=0\b/.test(c))
console.log(bad.length ? `BUG PRESENT: ${bad.length}/3 maxAge:0 cookies lack Max-Age=0` : 'OK')
process.exit(bad.length ? 1 : 0)
