const parse=require('../../../../../repos/validation-2026-09-27/nonlinux/ljharb-shell-quote').parse;
for(const [input,env,expected] of [['a$!b',{'!':'BANG'},'aBANGb'],['"x$!y"',{'!':'B'},'xBy'],['a$#b',{'#':'H'},'aHb']]){
 const actual=parse(input,env);console.log(JSON.stringify({input,env,expected,actual,bug:actual[0]!==expected}));
}
