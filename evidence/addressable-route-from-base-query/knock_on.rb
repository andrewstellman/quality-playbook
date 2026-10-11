# Before/after check for route_from. Prints one line per (target, base) pair:
#   route, and whether join(base, route) == target (the round trip #126 describes).
$LOAD_PATH.unshift(File.join(ARGV[0], "lib"))
require "addressable/uri"
paths   = ["", "/", "/file.txt", "/a/b", "/a/b/", "/a:b", "/dir/a:b", "/a%20b", "/x/../y", "/a/b/c.html"]
queries = [nil, "", "x=1", "y=2"]
frags   = [nil, "f"]
hosts   = ["http://example.com", "https://example.com", "http://other.example"]
uris = []
hosts.each { |h| paths.each { |p| queries.each { |q| frags.each { |f|
  u = h + p; u += "?" + q if q; u += "#" + f if f; uris << u } } } }
uris.each do |t|
  uris.each do |b|
    begin
      r = Addressable::URI.parse(t).route_from(b)
      back = Addressable::URI.join(b, r)
      ok = (back.normalize == Addressable::URI.parse(t).normalize)
      puts "#{t}\t#{b}\t#{r.to_s.inspect}\t#{ok ? 'roundtrip' : 'NO-ROUNDTRIP -> ' + back.to_s}"
    rescue => e
      puts "#{t}\t#{b}\tRAISES #{e.class}"
    end
  end
end
