import { RouteMatchers } from '/tmp/adonw/src/router/matchers.ts'
import { RouterFactory } from '/tmp/adonw/factories/router.ts'

const m = new RouteMatchers().uuid()
const cases = [
  '78fee49a-3d79-43bc-b93f-1ac4ba9e925b', // valid lowercase
  '78FEE49A-3D79-43BC-B93F-1AC4BA9E925B', // valid uppercase
  'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz', // non-hex lowercase
  'ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ', // non-hex uppercase
]
for (const c of cases) console.log(`matcher.test(${c}) = ${m.match.test(c)}`)

const router = new RouterFactory().create()
router.get('posts/:id', '#controllers/posts.show').where('id', router.matchers.uuid())
router.commit()
const hit = router.match('/posts/gggggggg-gggg-gggg-gggg-gggggggggggg', 'GET', false)
console.log('router.match(/posts/gggggggg-...) =>', hit ? JSON.stringify(hit.params) : null)

const bug = m.match.test(cases[2]) || hit !== null
console.log(bug ? 'BUG PRESENT' : 'bug absent')
process.exit(bug ? 1 : 0)
