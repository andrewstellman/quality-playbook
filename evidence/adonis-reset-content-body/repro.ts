import net from 'node:net'
import { createServer } from 'node:http'
import { HttpResponseFactory } from '/tmp/adonw/factories/response.ts'
import { RouterFactory } from '/tmp/adonw/factories/router.ts'
import { EncryptionFactory } from '/tmp/adonw/node_modules/@boringnode/encryption/build/factories/main.js'

const encryption = new EncryptionFactory().create()
const router = new RouterFactory().merge({ encryption }).create()

const server = createServer((req, res) => {
  const response = new HttpResponseFactory().merge({ req, res, encryption, router }).create()
  if (req.url === '/reset') response.status(205).send('some body')
  else if (req.url === '/helper') { response.resetContent() }
  else response.status(200).send('second')
  response.finish()
})
server.listen(0, '127.0.0.1', () => {
  const { port } = server.address() as any
  const sock = net.connect(port, '127.0.0.1')
  let raw = ''
  sock.on('data', (d) => (raw += d.toString('latin1')))
  // two pipelined requests on one keep-alive connection
  sock.write('GET /reset HTTP/1.1\r\nHost: x\r\n\r\nGET /next HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n')
  sock.on('end', () => {
    console.log('--- raw wire bytes (205 then 200 on one connection) ---')
    console.log(JSON.stringify(raw))
    const first = raw.split('HTTP/1.1 200')[0]
    const head = first.split('\r\n\r\n')[0]
    const body = first.slice(head.length + 4)
    console.log('205 headers:', JSON.stringify(head))
    console.log('205 body bytes after headers:', JSON.stringify(body))
    const bug = /content-length:\s*\d+/i.test(head) && body.length > 0
    console.log(bug ? 'BUG PRESENT: 205 response carries content' : 'OK: 205 has no content')
    server.close()
    process.exit(bug ? 1 : 0)
  })
})
