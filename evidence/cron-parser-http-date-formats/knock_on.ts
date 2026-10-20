// Run from a checkout root: TZ=UTC ./node_modules/.bin/ts-node <path>/knock_on.ts
// Prints one line per (input, tz) through the CronDate constructor, and one line per
// input through CronExpressionParser.parse(currentDate) + next().
import { CronDate } from './src/CronDate';
import { CronExpressionParser } from './src/CronExpressionParser';

const inputs: string[] = [
  '2021-01-04T11:00:00.000+02:00', // ISO
  '2021-01-04', // ISO date only
  'Mon, 4 Jan 2021 10:00:00 +0100', // RFC 2822
  'Mon, 4 Jan 2021 10:00:00', // RFC 2822 without offset (read in tz)
  '2021-01-04 10:00:00', // SQL
  'Sun, 06 Nov 1994 08:49:37 GMT', // HTTP IMF-fixdate (parses today via RFC 2822)
  'Sunday, 06-Nov-94 08:49:37 GMT', // HTTP RFC 850 (threw)
  'Sun Nov  6 08:49:37 1994', // HTTP asctime (threw)
  'Sun Nov 06 08:49:37 1994', // asctime, zero-padded day
  'Monday, 06-Nov-94 08:49:37 GMT', // RFC 850, wrong weekday for that date
  'Sun Nov  6 08:49:37 94', // asctime, two-digit year
  'Sun Nov  6 25:49:37 1994', // asctime, hour out of range
  'Sunday, 31-Feb-94 08:49:37 GMT', // RFC 850, impossible day
  'not a date', // invalid
  '', // empty string (falsy: becomes now, so skipped below)
  '1994-11-06T08:49:37Z', // ISO with Z
];
const zones = ['UTC', 'Europe/Athens', 'America/New_York'];

function show(fn: () => string): string {
  try {
    return fn();
  } catch (e) {
    return 'THROWS ' + (e instanceof Error ? e.message : String(e));
  }
}

for (const s of inputs) {
  if (s === '') continue;
  for (const tz of zones) {
    console.log(`CronDate  tz=${tz.padEnd(17)} ${JSON.stringify(s).padEnd(40)} -> ${show(() => new CronDate(s, tz).toISOString() as string)}`);
  }
}
console.log(`CronDate  tz=undefined         ${JSON.stringify('Sun Nov  6 08:49:37 1994').padEnd(40)} -> ${show(() => new CronDate('Sun Nov  6 08:49:37 1994').toISOString() as string)}`);

// Through the parser: currentDate, startDate and endDate strings, then next().
for (const s of ['Sunday, 06-Nov-94 08:49:37 GMT', 'Sun Nov  6 08:49:37 1994', 'Mon, 4 Jan 2021 10:00:00 +0100', 'not a date']) {
  console.log(
    `parse     currentDate=${JSON.stringify(s).padEnd(34)} tz=Europe/Athens next('0 * * * *') -> ${show(() =>
      String(CronExpressionParser.parse('0 * * * *', { currentDate: s, tz: 'Europe/Athens' }).next().toISOString()),
    )}`,
  );
}
console.log(
  `parse     startDate=asctime endDate=RFC850 count -> ${show(() => {
    const it = CronExpressionParser.parse('0 * * * *', {
      currentDate: '1994-11-06T00:00:00Z',
      startDate: 'Sun Nov  6 08:49:37 1994',
      endDate: 'Sunday, 06-Nov-94 12:00:00 GMT',
      tz: 'UTC',
    });
    const out: string[] = [];
    while (it.hasNext()) out.push(String(it.next().toISOString()));
    return out.join(',');
  })}`,
);
