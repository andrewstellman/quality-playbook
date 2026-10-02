exec(open('docs/research/triage-2026-09-27/nonlinux/evidence/check-disclosures.py').read().split('queries=')[0])
queries={'aiohttp-all-readuntil':'repo:aio-libs/aiohttp readuntil','defu-exact':'repo:unjs/defu "DefuInstance"','flatted-all-python':'repo:WebReflection/flatted python'}
out={}
for k,q in queries.items():
 try:
  req=urllib.request.Request('https://api.github.com/search/issues?q='+urllib.parse.quote(q),headers={'User-Agent':'QPB-historical-triage'})
  d=json.load(urllib.request.urlopen(req,timeout=20));out[k]={'query':q,'total_count':d['total_count'],'items':[{a:i.get(a) for a in ['number','title','html_url','state','created_at','body','pull_request']} for i in d['items']]};print(k,d['total_count'])
 except Exception as e:out[k]={'error':str(e)}
 time.sleep(2)
Path('docs/research/triage-2026-09-27/nonlinux/evidence/extra-disclosure-search.json').write_text(json.dumps(out,indent=2)+'\n')
