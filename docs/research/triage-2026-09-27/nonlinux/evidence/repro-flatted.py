from pathlib import Path
import importlib.util,json
path=Path('repos/validation-2026-09-27/nonlinux/flatted/python/flatted.py').resolve()
spec=importlib.util.spec_from_file_location('actual_flatted',path);f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
a,b={'x':1},{'x':1}
original=[a,b]
encoded=f.stringify(original);decoded=f.parse(encoded)
print('module',path)
print('original distinct',original[0] is not original[1]);print('encoded',encoded);print('decoded distinct',decoded[0] is not decoded[1])
decoded[0]['x']=2;print('after mutating first',decoded)
assert original[0] is not original[1]
assert decoded[1]['x']==2,'Historical bug no longer present'
print('CONFIRMED: distinct equal objects alias after roundtrip')
