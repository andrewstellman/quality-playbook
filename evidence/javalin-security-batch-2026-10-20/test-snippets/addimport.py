import sys
f, imp = sys.argv[1:3]
lines = open(f).read().split('\n')
line = 'import ' + imp
if line in lines: sys.exit()
idx = [i for i, l in enumerate(lines) if l.startswith('import ')]
pos = next((i for i in idx if lines[i] > line), idx[-1] + 1)
lines.insert(pos, line)
# if we landed right after a blank line that separates import groups, move above it
if pos>0 and lines[pos-1]=='' and pos-2>=0 and lines[pos-2].startswith('import '):
    lines.pop(pos); lines.insert(pos-1, line)
open(f, 'w').write('\n'.join(lines))
