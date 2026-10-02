import re, glob, os, collections, json, statistics
rows=json.load(open("unblind/rows.json"))  # from test 1: has hits per (repo,id)
byid={(r["repo"],r["id"]):r for r in rows}
LEV={"line":1,"nearby":2,"input":3,"trace":4}
cls=collections.defaultdict(dict)
for f in sorted(glob.glob("classifications-2/*-*.md")):
    repo,who=os.path.basename(f)[:-3].split("-")
    for l in open(f):
        m=re.match(r"\s*("+repo+r"-\d+)\s*\|\s*(line|nearby|input|trace)\s*\|",l)
        if m: cls[(repo,m.group(1))][who]=m.group(2)
out=[]
for k,d in cls.items():
    r=byid.get(k)
    if not r: continue
    levels=[d[w] for w in sorted(d)]
    maj=collections.Counter(levels).most_common(1)[0]
    mean_level=statistics.mean(LEV[x] for x in levels)
    out.append(dict(repo=k[0],id=k[1],n=r["n"],hits=r["hits"],rate=r["rate"],levels=levels,maj=maj[0],agree=maj[1]/len(levels),mean_level=mean_level,target=r["target"],loc=r["loc"],sonnet=[d[w] for w in sorted(d) if w.startswith("S")],opus=[d[w] for w in sorted(d) if w.startswith("O")]))
json.dump(out,open("unblind/rows2.json","w"),indent=1)
main=[r for r in out if r["n"]==20]
print("n classified:",len(out),"main:",len(main))
def summ(rs,label):
    print(f"\n== {label} (n={len(rs)})")
    by=collections.defaultdict(list)
    for r in rs: by[r["maj"]].append(r["rate"])
    for t in ["line","nearby","input","trace"]:
        v=by.get(t,[])
        if v: print(f"{t:7s} n={len(v):3d} mean={statistics.mean(v):.2f} median={statistics.median(v):.2f} zero={sum(1 for x in v if x==0)} >=40%={sum(1 for x in v if x>=0.4)}")
summ(main,"majority level, 5 repos")
summ([r for r in main if r["agree"]==1.0],"unanimous only")
# by mean level bucket
by=collections.defaultdict(list)
for r in main: by[round(r["mean_level"]*2)/2].append(r["rate"])
print("\nby mean level (0.5 steps):",{k:(len(v),round(statistics.mean(v),2)) for k,v in sorted(by.items())})
# correlation
import math
xs=[r["mean_level"] for r in main]; ys=[r["rate"] for r in main]
mx,my=statistics.mean(xs),statistics.mean(ys)
cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys)); sx=math.sqrt(sum((x-mx)**2 for x in xs)); sy=math.sqrt(sum((y-my)**2 for y in ys))
print("pearson r(mean_level, hit rate) =",round(cov/(sx*sy),3))
# spearman
def rank(v):
    s=sorted(range(len(v)),key=lambda i:v[i]); rk=[0]*len(v)
    i=0
    while i<len(s):
        j=i
        while j+1<len(s) and v[s[j+1]]==v[s[i]]: j+=1
        for t in range(i,j+1): rk[s[t]]=(i+j)/2+1
        i=j+1
    return rk
rx,ry=rank(xs),rank(ys); mrx,mry=statistics.mean(rx),statistics.mean(ry)
print("spearman rho =",round(sum((a-mrx)*(b-mry) for a,b in zip(rx,ry))/math.sqrt(sum((a-mrx)**2 for a in rx)*sum((b-mry)**2 for b in ry)),3))
print("\nagreement: unanimous",sum(1 for r in out if r["agree"]==1.0),"of",len(out),"; mean",round(statistics.mean(r["agree"] for r in out),3))
sc=collections.Counter(x for r in out for x in r["sonnet"]); oc=collections.Counter(x for r in out for x in r["opus"])
print("Sonnet:",dict(sc)); print("Opus:",dict(oc))
print("\nTARGETS")
for r in out:
    if r["target"]: print(f"{r['target']:30s} {r['id']:12s} hits={r['hits']}/{r['n']} levels={r['levels']} maj={r['maj']} mean={r['mean_level']:.1f}")
print("\nHIGH-FREQ (>=8/20):")
for r in sorted(main,key=lambda r:-r["hits"]):
    if r["hits"]>=8: print(f"{r['id']:12s} {r['hits']:2d} maj={r['maj']:7s} mean={r['mean_level']:.1f} {r['loc'][:55]}")
print("\nZERO-HIT findings:")
for r in main:
    if r["hits"]==0: print(f"{r['id']:12s} maj={r['maj']:7s} levels={r['levels']}")
print("\ntrace-majority findings:")
for r in main:
    if r["maj"]=="trace": print(f"{r['id']:12s} hits={r['hits']} levels={r['levels']}")
