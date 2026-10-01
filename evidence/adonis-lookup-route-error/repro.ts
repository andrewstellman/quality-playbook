import { RouterFactory } from '/tmp/adonw/factories/router.ts'
import { errors, ExceptionHandler } from '/tmp/adonw/index.ts'

const router = new RouterFactory().create()
router.get('/users/:id', () => {}).as('users.show')
router.commit()

function probe(label: string, fn: () => unknown) {
  try { fn(); console.log(label, '-> no throw'); return false }
  catch (e: any) {
    const isE = e instanceof errors.E_CANNOT_LOOKUP_ROUTE
    console.log(label, '->', e.constructor.name, JSON.stringify(e.message), 'code=', e.code, 'status=', e.status, 'instanceof E_CANNOT_LOOKUP_ROUTE=', isE)
    return !isE ? e : false
  }
}
const e1 = probe('router.findOrFail("missing")', () => router.findOrFail('missing'))
const e2 = probe('router.urlBuilder.urlFor("missing")', () => (router.urlBuilder.urlFor as any)('missing'))
const e3 = probe('router.findOrFail("users.show", undefined, "POST")', () => router.findOrFail('users.show', undefined, 'POST'))

class H extends ExceptionHandler { check(e: any) { return this.shouldReport(this.toHttpError(e) as any) } }
const h = new H()
if (e1) console.log('ExceptionHandler.shouldReport(actual error) =', h.check(e1))
console.log('ExceptionHandler.shouldReport(new E_CANNOT_LOOKUP_ROUTE) =', h.check(new errors.E_CANNOT_LOOKUP_ROUTE(['missing'])))

const bug = Boolean(e1 || e2 || e3)
console.log(bug ? 'BUG PRESENT' : 'BUG ABSENT')
process.exit(bug ? 1 : 0)
