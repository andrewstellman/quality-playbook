import '/tmp/adonw/node_modules/reflect-metadata/Reflect.js'
import supertest from '/tmp/adonw/node_modules/supertest/index.js'
import { createServer } from 'node:http'
import { AppFactory } from '/tmp/adonw/node_modules/@adonisjs/application/build/factories/main.js'
import { ServerFactory } from '/tmp/adonw/factories/server_factory.ts'

const app = new AppFactory().create(new URL('file:///tmp/adonw/tests/app/'), () => {})
await app.init()
const server = new ServerFactory().merge({ app }).create()
const httpServer = createServer(server.handle.bind(server))
server.use([])
const router = server.getRouter()
router.get('/new', async () => 'new').as('new')
const opts: any = { qs: { a: 1 } }
// @ts-ignore  brisk redirect with options (3rd arg) carrying qs
router.on('/old').redirect('new', {}, opts)
await server.boot()

const locs: string[] = []
for (let i = 0; i < 3; i++) {
  const res = await supertest(httpServer).get('/old')
  locs.push(`${res.status} ${res.headers.location}`)
}
console.log('locations:', locs)
console.log('options object after requests:', JSON.stringify(opts), 'qs' in opts ? `(qs key present, value ${opts.qs})` : '')
const bug = locs.some((l) => !l.endsWith('/new?a=1'))
console.log(bug ? 'BUG PRESENT' : 'no bug')
process.exit(bug ? 1 : 0)
