// BUG-010 repro: crontab lines named __proto__ / constructor through CronFileParser
// Run from the clone root after `npm run build`: node ../notes/repro-bug010.cjs
const fs = require('fs');
const os = require('os');
const path = require('path');
const { CronFileParser } = require(path.resolve(process.cwd(), 'dist/index.js'));

const content = ['__proto__', '__proto__=polluted', '0 0 * * * ok', 'constructor', 'FOO=bar'].join('\n');
const file = path.join(os.tmpdir(), 'bug010-crontab');
fs.writeFileSync(file, content);
console.log('crontab content:', JSON.stringify(content));

const result = CronFileParser.parseFileSync(file);
console.log('errors keys:', Object.keys(result.errors));
console.log('errors proto is Object.prototype:', Object.getPrototypeOf(result.errors) === Object.prototype);
console.log('errors proto:', Object.getPrototypeOf(result.errors));
console.log('errors.message (inherited through replaced proto):', result.errors.message);
console.log('JSON.stringify(errors):', JSON.stringify(result.errors));
console.log('variables keys:', Object.keys(result.variables));
console.log('variables proto is Object.prototype:', Object.getPrototypeOf(result.variables) === Object.prototype);
console.log('variables:', result.variables);
console.log('expressions count:', result.expressions.length);
console.log('global Object.prototype polluted? ({}).message:', ({}).message, '({}).polluted:', ({}).polluted);

CronFileParser.parseFile(file).then((r) => {
  console.log('async parseFile: errors proto is Object.prototype:', Object.getPrototypeOf(r.errors) === Object.prototype, '| errors keys:', Object.keys(r.errors), '| variables keys:', Object.keys(r.variables));
});
