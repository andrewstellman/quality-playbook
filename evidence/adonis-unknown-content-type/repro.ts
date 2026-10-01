import { createServer } from 'node:http'
import supertest from '/tmp/adonw/node_modules/supertest/index.js'
import { HttpResponseFactory } from '/tmp/adonw/factories/response.ts'

const dir = '/tmp/adonv/BUG-028/files'
const cases: Array<[string, (r: any) => void]> = [
  ['download(LICENSE)', (r) => r.download(`${dir}/LICENSE`)],
  ['download(data.unknownext)', (r) => r.download(`${dir}/data.unknownext`)],
  ["type('.nope').send('x')", (r) => r.type('.nope').send('x')],
  ["control: download(a.txt)", (r) => r.download(`${dir}/a.txt`)],
  ["control: send('x') no type()", (r) => r.send('x')],
]
let bug = false
for (const [name, fn] of cases) {
  const server = createServer((req, res) => {
    const response = new HttpResponseFactory().merge({ req, res }).create()
    fn(response)
    response.finish()
  })
  const res = await supertest(server).get('/')
  const ct = res.headers['content-type']
  console.log(`${name.padEnd(32)} status=${res.status} content-type=${JSON.stringify(ct)}`)
  if (ct === 'false') bug = true
}
console.log(bug ? 'BUG PRESENT: Content-Type "false" emitted' : 'bug absent')
process.exit(bug ? 1 : 0)
