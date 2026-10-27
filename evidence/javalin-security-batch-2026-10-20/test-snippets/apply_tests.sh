#!/bin/bash
# usage: apply_tests.sh <src-root> <bug...>   inserts the regression test(s) for the given bug numbers
set -e
S=$1; shift; T=/tmp/claude-0/sec/javalin/tests; J=$S/javalin/src/test/java/io/javalin
addimport() { python3 /tmp/claude-0/sec/javalin/tests/addimport.py "$1" "$2"; }
for b in "$@"; do case $b in
 055) python3 $T/insert.py $J/staticfiles/TestStaticFiles.kt 'fun `directory root returns simple 404' $T/055.kt ;;
 028) python3 $T/insert.py $J/TestRequest.kt 'fun `servlet-context is not null`' $T/028.kt; addimport $J/TestRequest.kt io.javalin.testing.httpCode ;;
 065) python3 $T/insert.py $J/TestRequest.kt 'fun `basic auth filter plugin works`' $T/065.kt; addimport $J/TestRequest.kt java.util.Base64 ;;
 050) python3 - $J/TestContextRouteRoles.kt $T/050.kt <<'PY'
import sys; f,s=sys.argv[1:3]; src=open(f).read().rstrip('\n'); assert src.endswith('}'); body=src[:-1].rstrip('\n')+'\n\n'+open(s).read().rstrip('\n')+'\n\n}\n'; open(f,'w').write(body)
PY
   addimport $J/TestContextRouteRoles.kt io.javalin.http.UnauthorizedResponse; addimport $J/TestContextRouteRoles.kt kong.unirest.HttpMethod ;;
 037) python3 $T/insert.py $J/websocket/TestWsUpgrade.kt 'fun `wsBeforeUpgrade exception pattern' $T/037.kt; addimport $J/websocket/TestWsUpgrade.kt io.javalin.Javalin; addimport $J/websocket/TestWsUpgrade.kt io.javalin.http.Header; addimport $J/websocket/TestWsUpgrade.kt kong.unirest.Unirest ;;
 020) python3 $T/insert.py $J/TestSse.kt 'fun `sse does not work without text-event-stream' $T/020.kt ;;
 033) python3 $T/insert.py $J/TestHttpResponseExceptions.kt 'fun `response is formatted as json if client wants json`' $T/033.kt ;;
esac; done
