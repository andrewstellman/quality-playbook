import urllib.request,urllib.parse,json,time
from pathlib import Path
queries={
'chi-compression':'repo:go-chi/chi "q=0"',
'chi-supress':'repo:go-chi/chi SupressNotFound',
'chi-charset':'repo:go-chi/chi charset quoted',
'shell-special':'repo:ljharb/shell-quote special parameter',
'minimatch-print':'repo:isaacs/minimatch "[:print:]"',
'flatted-python':'repo:WebReflection/flatted python equal',
'defu-types':'repo:unjs/defu extend types',
'aiohttp-readuntil':'repo:aio-libs/aiohttp readuntil boundary',
'immutable-repeat':'repo:immutable-js/immutable-js Repeat lastIndexOf'}
out={}
for key,q in queries.items():
 try:
  req=urllib.request.Request('https://api.github.com/search/issues?q='+urllib.parse.quote(q),headers={'User-Agent':'QPB-historical-triage'})
  data=json.load(urllib.request.urlopen(req,timeout=20));out[key]={'query':q,'total_count':data['total_count'],'items':[{k:i.get(k) for k in ['number','title','html_url','state','created_at','updated_at','body','pull_request']} for i in data['items']]};print(key,data['total_count'])
 except Exception as e:out[key]={'query':q,'error':str(e)};print(key,str(e))
 time.sleep(2)
Path('docs/research/triage-2026-09-27/nonlinux/evidence/disclosure-search.json').write_text(json.dumps(out,indent=2)+'\n')
