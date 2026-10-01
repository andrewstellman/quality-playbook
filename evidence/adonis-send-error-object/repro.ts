import supertest from '/tmp/adonw/node_modules/supertest/index.js'
import { AppFactory } from '/tmp/adonw/node_modules/@adonisjs/application/build/factories/main.js'
import { EncryptionFactory } from '/tmp/adonw/node_modules/@boringnode/encryption/build/factories/main.js'
import { RouterFactory } from '/tmp/adonw/factories/router.ts'
import { httpServer } from '/tmp/adonw/factories/http_server.ts'
import { HttpResponseFactory } from '/tmp/adonw/factories/response.ts'

const encryption = new EncryptionFactory().create()
const app = new AppFactory().create(new URL('file:///tmp/adonv/BUG-014/app/'), () => {})
const router = new RouterFactory().merge({ app, encryption }).create()

async function probe(label: string, body: any) {
  const { url } = await httpServer.create((req, res) => {
    const response = new HttpResponseFactory().merge({ req, res, encryption, router }).create()
    response.send(body)
    response.finish()
  })
  const r = await supertest(url).get('/')
  console.log(`${label}: status=${r.status} content-type=${r.headers['content-type']} body=${JSON.stringify(r.text)}`)
  return r
}

await probe('RegExp (sibling, documented same rule)', /abc/g)
const r = await probe('Error', new Error('boom'))
await probe('TypeError', new TypeError('bad'))
const buggy = r.text !== 'Error: boom'
console.log(buggy ? 'BUG PRESENT: Error serialized as JSON, not toString()' : 'OK: Error serialized via toString()')
process.exit(buggy ? 1 : 0)
