Title: Template#match ReDoS (GHSA-h27x-rffw-24p4) is not fully fixed in 2.9.0 for {/var*}, {.var*} and {;var*}

Ecosystem: RubyGems
Package: addressable
Affected versions: <= 2.9.0 and main at d298c9f
Patched versions: none yet
Severity: Medium (same impact as GHSA-h27x-rffw-24p4, but MRI 3.2 and later are not affected)
CWE: CWE-1333 Inefficient Regular Expression Complexity
Credit: Andrew Stellman

Description

Summary
GHSA-h27x-rffw-24p4 / CVE-2026-35611 lists 2.9.0 as fully remediating the explode-modifier ReDoS. On regex engines without match memoization (MRI 3.1 and earlier, and by the advisory's own table JRuby and TruffleRuby), Template#match and Template#extract on 2.9.0 still backtrack exponentially for exploded /, . and ; expressions when the input starts with the operator's leading character. A 26-character string takes 20 to 24 seconds to reject on MRI 3.1.6.

Where
lib/addressable/template.rb, parse_new_template_pattern, explode branch (current main d298c9f, lines 1026-1032):

    joiner_pattern = operator.nil? ? joiner : "#{joiner}?"
    "(?<#{name}>#{seg}(?:#{joiner_pattern}#{seg})*)?"

The 2.9.0 fix made the joiner mandatory only for the default operator. For /, . and ; the joiner is still optional and each member is a lazy repetition, so a run of members can be split in exponentially many ways. For ; the member pattern UNRESERVED*=?UNRESERVED*? is also ambiguous on its own when a member has no '='. The regression specs added in 2.9.0 for {/foo*}, {.foo*} and {;foo*} use payloads that do not begin with '/', '.' or ';' (for example ("a/" * 1000) + "!"), so the regex fails at the leader and the vulnerable branch is never exercised.

Reproducer (MRI 3.1.6, addressable at d298c9f, pure IDNA)

    require "addressable/template"
    Addressable::Template.new("{;x*}").match(";" + "x=a;" * 6 + "!")

Measured time to return nil (two separate runs on the same machine; "len" is the input length):

    template        input                         MRI 3.1.6          MRI 3.2.6 / 3.3.6
    {;x*}           ";" + "x=a;"*5 + "!"  (22)     0.9 to 1.5 s       < 1 ms
    {;x*}           ";" + "x=a;"*6 + "!"  (26)     20.5 to 24.2 s     < 1 ms
    {;x*}           ";" + "x=a;"*7 + "!"  (30)     > 60 s (killed)    < 1 ms
    /foo{/segs*}    "/foo/" + "a/"*20 + "!" (46)   0.6 to 0.9 s       < 1 ms
    /foo{/segs*}    "/foo/" + "a/"*22 + "!" (50)   1.8 to 4.4 s       < 1 ms
    /foo{/segs*}    "/foo/" + "a/"*24 + "!" (54)   8.4 to 18.6 s      < 1 ms
    {.x*}           "." + "a."*22 + "!"   (46)     1.2 to 4.5 s       < 1 ms
    {.x*}           "." + "a."*24 + "!"   (50)     6.2 to 16.0 s      < 1 ms

Time grows by roughly 3x to 5x for every two added members on the / and . forms and by roughly 15x per added member on the ; form. {?x*} and {&x*} are not affected because their member pattern requires '=' and is unambiguous. JRuby and TruffleRuby were not tested; the advisory lists them as lacking the memoization that masks the problem on MRI 3.2+.

The reproducer from the long-open public issue #364 ("{scheme}://{host}{/path*}{?query*}" against "http://host.com/abcdefghijklmnopqrstuvwxyz?a") still does not finish within 60 seconds on 2.9.0 under MRI 3.1.6, which suggests that issue was not actually resolved by 2.9.0 either.

Impact
Denial of service (CPU exhaustion) for applications that call Template#match or Template#extract on attacker-supplied URIs with a template containing {/var*}, {.var*} or {;var*}, such as routers and API clients that match incoming URLs, when running on MRI 3.1 or earlier, JRuby or TruffleRuby. This is the same impact and threat model as GHSA-h27x-rffw-24p4.

Affected versions
All releases that support the explode modifier through 2.9.0 (current main d298c9f). MRI 3.2 and later mask it through Onigmo memoization.

Suggested fix
Make the joiner mandatory for every operator and give each ;, ? and & member a single parse. The patch below does this:

    seg = case operator
          when '+', '#' then "(?>#{RESERVED_NO_COMMA}*)"
          when ';' then "#{UNRESERVED}*(?:=#{UNRESERVED}*)?"
          when '?', '&' then "#{UNRESERVED}*=#{UNRESERVED}*"
          else group
          end
    "(?<#{name}>#{seg}(?:#{joiner}#{seg})*)?"

With it, every case above returns nil in under 15 ms at 4,000 members on MRI 3.1.6, including the issue #364 inputs. The full suite passes (1438 examples, 0 failures) on MRI 3.1.6 and 3.3.6, and the five new regression specs (payloads that begin with the operator character) time out without the fix and pass with it. Existing captures are unchanged, including the "{;hash*,first}" match spec.

Since the published advisory states 2.9.0 is fully patched, you may want to update GHSA-h27x-rffw-24p4 or publish a follow-up advisory once a release is out.

Found with the Quality Playbook (github.com/andrewstellman/quality-playbook), an AI code-review tool I maintain. Claude reproduced it and wrote the patch and test, and I reviewed them.

