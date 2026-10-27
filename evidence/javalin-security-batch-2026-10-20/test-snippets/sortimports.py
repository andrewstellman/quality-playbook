import sys
for f in sys.argv[1:]:
    lines=open(f).read().split('\n')
    idx=[i for i,l in enumerate(lines) if l.startswith('import ')]
    if not idx: continue
    a,b=idx[0],idx[-1]
    block=[l for l in lines[a:b+1] if l.startswith('import ')]
    assert len(block)==b-a+1, f
    lines[a:b+1]=sorted(set(block))
    open(f,'w').write('\n'.join(lines))
