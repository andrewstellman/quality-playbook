// Knock-on probe for BUG-004. Prints one line per (reference, phrase) to the file named by KNOCK_OUT.
// Run by knock_on.sh in a checkout, once at the base commit and once at the fixed commit.
import * as chrono from "../src";
import * as fs from "fs";

const refs: { label: string; ref: any }[] = [
    { label: "Date 2012-07-31T22:00Z", ref: new Date("2012-07-31T22:00:00Z") },
    { label: "{instant} 2012-07-31T22:00Z", ref: { instant: new Date("2012-07-31T22:00:00Z") } },
    { label: "{instant,tz:null} 2012-07-31T22:00Z", ref: { instant: new Date("2012-07-31T22:00:00Z"), timezone: null } },
    { label: "{instant,tz:JST} 2012-07-31T22:00Z", ref: { instant: new Date("2012-07-31T22:00:00Z"), timezone: "JST" } },
    { label: "{instant,tz:540} 2012-07-31T22:00Z", ref: { instant: new Date("2012-07-31T22:00:00Z"), timezone: 540 } },
    { label: "{instant,tz:EST} 2012-08-01T03:00Z", ref: { instant: new Date("2012-08-01T03:00:00Z"), timezone: "EST" } },
    { label: "{instant,tz:JST} 2012-08-01T12:00Z (mid-day)", ref: { instant: new Date("2012-08-01T12:00:00Z"), timezone: "JST" } },
    { label: "{instant,tz:JST} 2012-12-31T22:00Z", ref: { instant: new Date("2012-12-31T22:00:00Z"), timezone: "JST" } },
    { label: "{instant,tz:JST} 2012-08-04T22:00Z", ref: { instant: new Date("2012-08-04T22:00:00Z"), timezone: "JST" } },
    { label: "{instant,tz:JST} 2021-08-16T20:00Z", ref: { instant: new Date("2021-08-16T20:00:00Z"), timezone: "JST" } },
    { label: "{instant,tz:JST} 2012-07-31T20:59Z (05:59 JST)", ref: { instant: new Date("2012-07-31T20:59:00Z"), timezone: "JST" } },
    { label: "{instant,tz:JST} 2012-07-31T22:00Z (07:00 JST)", ref: { instant: new Date("2012-07-31T22:00:00Z"), timezone: "JST" } },
];

const phrases = [
    "this month",
    "this week",
    "this year",
    "last night",
    "Feb 15",
    "15 Feb",
    "2/15",
    "February",
    "Feb 15, 2013",
    "today",
    "next month",
    "tomorrow at 5pm",
    "end of this month",
    "Deadline is this month",
];

test("knock-on probe", () => {
    const lines: string[] = [`process TZ=${process.env.TZ}`];
    for (const { label, ref } of refs) {
        lines.push(`## ref: ${label}`);
        for (const phrase of phrases) {
            let out: string;
            try {
                const results = chrono.parse(phrase, ref);
                out = results.length
                    ? results
                          .map((r) => {
                              const s = r.start;
                              return `index=${r.index} text=${JSON.stringify(r.text)} start=${s.get("year")}-${s.get("month")}-${s.get("day")} h=${s.get("hour")} date=${s.date().toISOString()}`;
                          })
                          .join(" | ")
                    : "(no result)";
            } catch (e) {
                out = "EXCEPTION " + e;
            }
            lines.push(`${phrase.padEnd(24)} ${out}`);
        }
    }
    fs.writeFileSync(process.env.KNOCK_OUT as string, lines.join("\n") + "\n");
});
