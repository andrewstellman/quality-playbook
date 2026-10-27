import sys
# usage: insert.py <file> <anchor-line-substring> <snippet-file>  : inserts snippet before the line containing the anchor
f, anchor, snip = sys.argv[1:4]
src = open(f).read().split('\n')
idx = next(i for i, l in enumerate(src) if anchor in l)
# back up to the @Test line above the anchor
while idx > 0 and src[idx-1].strip() == '@Test': idx -= 1
snippet = open(snip).read().rstrip('\n').split('\n')
src[idx:idx] = snippet + ['']
open(f, 'w').write('\n'.join(src))
