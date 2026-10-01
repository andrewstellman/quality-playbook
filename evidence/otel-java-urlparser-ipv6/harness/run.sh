#!/bin/bash
# Standalone javac + JUnit Platform harness for opentelemetry-java-instrumentation.
# Usage: run.sh <repo-root> <suite> [extra junit args...]
#   suite = api       : compiles instrumentation-api/src/main (all), runs semconv.http parser tests
#   suite = incubator : compiles instrumentation-api + instrumentation-api-incubator/src/main, runs net.internal UrlParserTest
#   suite = reactor   : compiles reactor-netty-1.0 UrlParser.java alone, runs its UrlParserTest
set -u
REPO=$1; SUITE=$2; shift 2
JAVA_HOME=/tmp/jdk25/root/usr/lib/jvm/java-25-openjdk-arm64
JAVAC=$JAVA_HOME/bin/javac; JAVA=$JAVA_HOME/bin/java
D=/tmp/deps
CP_MAIN=$D/opentelemetry-api-1.66.0.jar:$D/opentelemetry-context-1.66.0.jar:$D/opentelemetry-common-1.66.0.jar:$D/opentelemetry-api-incubator-1.66.0-alpha.jar:$D/opentelemetry-semconv-1.44.0.jar:$D/opentelemetry-semconv-incubating-1.44.0-alpha.jar:$D/auto-value-annotations-1.11.1.jar:$D/jsr305-3.0.2.jar:$D/error_prone_annotations-2.42.0.jar
CP_TEST=$D/opentelemetry-sdk-1.66.0.jar:$D/opentelemetry-sdk-common-1.66.0.jar:$D/opentelemetry-sdk-trace-1.66.0.jar:$D/opentelemetry-sdk-metrics-1.66.0.jar:$D/opentelemetry-sdk-logs-1.66.0.jar:$D/opentelemetry-sdk-testing-1.66.0.jar:$D/junit-platform-console-standalone-1.14.4.jar:$D/assertj-core-3.27.7.jar:$D/mockito-core-4.11.0.jar:$D/mockito-junit-jupiter-4.11.0.jar:$D/objenesis-3.3.jar:$D/byte-buddy-1.18.14.jar:$D/byte-buddy-agent-1.18.14.jar
OUT=$(mktemp -d /tmp/harness/out.XXXX)
echo "== harness: repo=$REPO suite=$SUITE HEAD=$(git -C $REPO rev-parse HEAD) dirty=$(git -C $REPO status --porcelain | wc -l)"
echo "== javac: $($JAVAC -version 2>&1)"
case $SUITE in
  api)
    find $REPO/instrumentation-api/src/main/java -name '*.java' > $OUT/main.txt
    $JAVAC -nowarn -proc:full -processorpath $D/auto-value-1.11.1.jar -cp $CP_MAIN -d $OUT/main @$OUT/main.txt 2>&1 | grep -v "^Note:" || true
    T=$REPO/instrumentation-api/src/test/java/io/opentelemetry/instrumentation/api/semconv/http
    # every test in the semconv.http (+ .internal) packages except the 3 that need
    # :testing-common / :instrumentation-api-incubator project dependencies
    find $T -name '*.java' | grep -v -e HttpClientMetricsTest -e HttpServerMetricsTest -e HttpSpanNameExtractorTest -e ValidRequestMethodsProvider > $OUT/test.txt
    echo $T/ValidRequestMethodsProvider.java >> $OUT/test.txt
    SEL="--select-package io.opentelemetry.instrumentation.api.semconv.http"
    ;;
  incubator)
    find $REPO/instrumentation-api/src/main/java -name '*.java' > $OUT/api.txt
    $JAVAC -nowarn -proc:full -processorpath $D/auto-value-1.11.1.jar -cp $CP_MAIN -d $OUT/main @$OUT/api.txt 2>&1 | grep -v "^Note:" || true
    IM=$REPO/instrumentation-api-incubator/src/main/java/io/opentelemetry/instrumentation/api/incubator/semconv
    IT=$REPO/instrumentation-api-incubator/src/test/java/io/opentelemetry/instrumentation/api/incubator/semconv
    # compile only UrlParser and its in-module consumers; -sourcepath pulls in what they reference
    ls $IM/net/internal/UrlParser.java $IM/service/peer/internal/ServicePeerResolver.java $IM/service/peer/ServicePeerAttributesExtractor.java $IM/http/HttpClientServicePeerAttributesExtractor.java > $OUT/main.txt
    $JAVAC -nowarn -proc:full -processorpath $D/auto-value-1.11.1.jar -sourcepath $REPO/instrumentation-api-incubator/src/main/java -cp $CP_MAIN:$OUT/main -d $OUT/main @$OUT/main.txt 2>&1 | grep -v "^Note:" || true
    ls $IT/net/internal/UrlParserTest.java $IT/service/peer/internal/ServicePeerResolverTest.java $IT/service/peer/ServicePeerAttributesExtractorTest.java $IT/http/HttpClientServicePeerAttributesExtractorTest.java > $OUT/test.txt
    # SemconvServiceStabilityUtil (a :testing-common helper with only api/semconv deps) is added from source
    echo $REPO/testing-common/src/main/java/io/opentelemetry/instrumentation/testing/junit/service/SemconvServiceStabilityUtil.java >> $OUT/test.txt
    SEL="--select-class io.opentelemetry.instrumentation.api.incubator.semconv.net.internal.UrlParserTest --select-class io.opentelemetry.instrumentation.api.incubator.semconv.service.peer.internal.ServicePeerResolverTest --select-class io.opentelemetry.instrumentation.api.incubator.semconv.service.peer.ServicePeerAttributesExtractorTest --select-class io.opentelemetry.instrumentation.api.incubator.semconv.http.HttpClientServicePeerAttributesExtractorTest"
    ;;
  reactor)
    echo $REPO/instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent/src/main/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParser.java > $OUT/main.txt
    $JAVAC -nowarn -cp $CP_MAIN -d $OUT/main @$OUT/main.txt 2>&1 | grep -v "^Note:" || true
    echo $REPO/instrumentation/reactor/reactor-netty/reactor-netty-1.0/javaagent-unit-tests/src/test/java/io/opentelemetry/javaagent/instrumentation/reactornetty/v1_0/UrlParserTest.java > $OUT/test.txt
    SEL="--select-class io.opentelemetry.javaagent.instrumentation.reactornetty.v1_0.UrlParserTest"
    ;;
esac
if [ -n "${SEL_OVERRIDE:-}" ]; then SEL=$SEL_OVERRIDE; fi
echo "== junit selection: $SEL"
$JAVAC -nowarn -cp $CP_MAIN:$CP_TEST:$OUT/main -d $OUT/test @$OUT/test.txt 2>&1 | grep -v "^Note:" || true
$JAVA --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED -jar $D/junit-platform-console-standalone-1.14.4.jar execute \
  --disable-banner --details=tree --disable-ansi-colors -cp $CP_MAIN:$CP_TEST:$OUT/main:$OUT/test $SEL "$@"
RC=$?
rm -rf $OUT
echo "== junit exit code: $RC"
exit $RC
