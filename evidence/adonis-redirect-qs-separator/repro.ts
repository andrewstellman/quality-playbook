import supertest from '/tmp/adonw/node_modules/supertest/index.js'
import { AppFactory } from '/tmp/adonw/node_modules/@adonisjs/application/build/factories/main.js'
import { EncryptionFactory } from '/tmp/adonw/node_modules/@boringnode/encryption/build/factories/main.js'
import { RouterFactory } from '/tmp/adonw/factories/router.ts'
import { httpServer } from '/tmp/adonw/factories/http_server.ts'
import { HttpResponseFactory } from '/tmp/adonw/factories/response.ts'

const app = new AppFactory().create(new URL('file:///tmp/adonv/BUG-004/app/'), () => {})
const encryption = new EncryptionFactory().create()
const router = new RouterFactory().merge({ app, encryption }).create()

async function run(label: string, fn: (r: any) => void, reqPath = '/') {
  const { url } = await httpServer.create((req, res) => {
    const response = new HttpResponseFactory().merge({ req, res, encryption, router }).create()
    fn(response)
    response.finish()
  })
  const { header } = await supertest(url).get(reqPath).redirects(0)
  console.log(`${label}: Location = ${header.location}`)
  return header.location as string
}

const a = await run('withQs("b","2").toPath("/foo?a=1")', (r) => r.redirect().withQs('b', '2').toPath('/foo?a=1'))
const b = await run('withQs().toPath("/foo?a=1") on GET /?b=2', (r) => r.redirect().withQs().toPath('/foo?a=1'), '/?b=2')
const c = await run('toPath("/foo?a=1") no qs (control)', (r) => r.redirect().toPath('/foo?a=1'))
const parsed = new URL(a, 'http://x').searchParams
console.log('destination parses a =', JSON.stringify(parsed.get('a')), ' b =', JSON.stringify(parsed.get('b')))
const bug = a.split('?').length > 2 || b.split('?').length > 2
console.log(bug ? 'BUG PRESENT: second "?" in Location' : 'no bug')
process.exit(bug ? 1 : 0)
