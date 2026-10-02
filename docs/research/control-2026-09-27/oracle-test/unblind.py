import re, glob, os, collections, json, statistics
base="."
repos=["aiohttp","chi","express","calibre","bionemo","otel","assertj"]
nruns={"otel":2,"assertj":2}
TYPES=["in-repo","implicit","known-external","fetch-external","none"]
# parse classifications
cls=collections.defaultdict(dict)  # cls[(repo,id)][classifier]=(type,conf)
for f in sorted(glob.glob("classifications/*.md")):
    repo,who=os.path.basename(f)[:-3].split("-")
    txt=open(f).read()
    for m in re.finditer(r"^### (.+?)\n(.*?)(?=^### |\Z)", txt, re.S|re.M):
        head,body=m.group(1),m.group(2)
        ids=re.findall(rf"{repo}-\d+",head)
        if not ids: continue
        t=re.search(r"^Type:\s*([a-z-]+)",body,re.M); c=re.search(r"^Confidence:\s*(high|medium|low)",body,re.M)
        if not t: continue
        for i in ids: cls[(repo,i)][who]=(t.group(1),c.group(1) if c else "?")
# idmaps (old->new) for renumbered repos
idmap={}
for repo in repos:
    p=f"unblind/idmap-{repo}.md"
    if os.path.exists(p):
        for l in open(p):
            mm=re.match(r"(\S+) -> (\S+)",l.strip())
            if mm: idmap[(repo,mm.group(1))]=mm.group(2)
# hits
hits={}; mentions={}
for repo in repos:
    for l in open(f"unblind/findings-{repo}-hits.md"):
        mm=re.match(r"\|\s*("+repo+r"-\d+)\s*\|(.*?)\|(.*?)\|",l)
        if not mm: continue
        old=mm.group(1); new=idmap.get((repo,old),old)
        inc=[x.strip() for x in mm.group(2).split(",") if "run" in x]
        men=[x.strip() for x in mm.group(3).split(",") if "run" in x]
        hits[(repo,new)]=inc; mentions[(repo,new)]=men
# targets (new ids)
targets={("chi","chi-22"):"chi GetHead under mount",("express","express-11"):"express maxAge<1s",("calibre","calibre-11"):"calibre OPDS hex->500",("bionemo","bionemo-03"):"bionemo THD remainder",("aiohttp","aiohttp-10"):"aiohttp readuntil"}
# find amplify target id: old bionemo-14
targets[("bionemo",idmap[("bionemo","bionemo-14")])]="bionemo AMPLIFY _pad_weights"
for k in targets:
    hits.setdefault(k,[]); mentions.setdefault(k,[])
# descriptions from blind lists
desc={}
for repo in repos:
    for l in open(f"findings-{repo}-blind.md"):
        mm=re.match(r"\|\s*("+repo+r"-\d+)\s*\|(.*?)\|(.*?)\|",l)
        if mm: desc[(repo,mm.group(1))]=(mm.group(2).strip(),mm.group(3).strip())
rows=[]
for (repo,i),d in sorted(cls.items(), key=lambda x:(repos.index(x[0][0]),int(x[0][1].split("-")[1]))):
    types=[v[0] for v in d.values()]
    maj=collections.Counter(types).most_common(1)[0]
    n=nruns.get(repo,20)
    h=len(hits.get((repo,i),[])); 
    opus=sum(1 for r in hits.get((repo,i),[]) if r.startswith("opus")); son=h-opus
    sonnet_types=[v[0] for k,v in d.items() if k.startswith("S")]; opus_types=[v[0] for k,v in d.items() if k.startswith("O")]
    rows.append(dict(repo=repo,id=i,n=n,hits=h,opus=opus,sonnet=son,rate=h/n,types=types,maj=maj[0],agree=maj[1]/len(types),
        sonnet_types=sonnet_types,opus_types=opus_types,target=targets.get((repo,i)),loc=desc.get((repo,i),("",""))[0],
        confs=[v[1] for v in d.values()]))
json.dump(rows,open("unblind/rows.json","w"),indent=1)
# summary by majority type (exclude otel/assertj n=2 from rate stats? include separately)
def summ(rs,label):
    print(f"\n== {label} (n findings={len(rs)})")
    by=collections.defaultdict(list)
    for r in rs: by[r["maj"]].append(r["rate"])
    for t in TYPES:
        v=by.get(t,[])
        if v: print(f"{t:15s} n={len(v):3d} mean hit rate={statistics.mean(v):.2f} median={statistics.median(v):.2f} zero-hit={sum(1 for x in v if x==0)} >=40%={sum(1 for x in v if x>=0.4)}")
main=[r for r in rows if r["n"]==20]
summ(main,"5 repos with 20 runs, majority type")
# unanimous only
summ([r for r in main if r["agree"]==1.0],"unanimous classifications only")
# agreement
print("\nagreement: mean fraction agreeing with majority =",round(statistics.mean(r["agree"] for r in rows),3))
print("unanimous:",sum(1 for r in rows if r["agree"]==1.0),"of",len(rows))
print("majority <=0.6:",sum(1 for r in rows if r["agree"]<=0.6))
# sonnet vs opus type distribution
sc=collections.Counter(t for r in rows for t in r["sonnet_types"]); oc=collections.Counter(t for r in rows for t in r["opus_types"])
print("\nSonnet type dist:",dict(sc)); print("Opus type dist:",dict(oc))
# targets
print("\nTARGETS")
for r in rows:
    if r["target"]: print(f"{r['target']:32s} {r['id']:12s} hits={r['hits']}/{r['n']} types={r['types']} maj={r['maj']}")
# high-frequency findings and their types
print("\nHIGH-FREQ (>=8/20) findings:")
for r in sorted(main,key=lambda r:-r["hits"]):
    if r["hits"]>=8: print(f"{r['id']:12s} {r['hits']:2d} maj={r['maj']:15s} agree={r['agree']:.2f} {r['loc'][:60]}")
print("\nfetch-external or none majority:")
for r in rows:
    if r["maj"] in ("fetch-external","none"): print(f"{r['id']:12s} hits={r['hits']}/{r['n']} types={r['types']}")
