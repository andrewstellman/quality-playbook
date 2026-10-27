package io.javalin.qpb

import io.javalin.Javalin
import io.javalin.http.staticfiles.Location
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import org.junit.jupiter.api.Test

class KnockOnStaticTest {
    @Test
    fun `knock-on: ordinary static requests before and after`() {
        val dir = Files.createTempDirectory("qpb-knock").toRealPath()
        for (name in listOf("plain.txt", "my file.txt", "café.txt", "a-b_c.d~e.txt", "sub/deep.txt", "secret/file.txt"))
            dir.resolve(name).also { Files.createDirectories(it.parent) }.let { Files.writeString(it, "content of $name") }
        val app = Javalin.create { cfg -> cfg.startup.showJavalinBanner = false; cfg.staticFiles.add(dir.toString(), Location.EXTERNAL); cfg.routes.before("/secret/*") { throw io.javalin.http.UnauthorizedResponse() } }.start(0)
        val client = HttpClient.newHttpClient()
        try {
            for (p in listOf("/plain.txt", "/my%20file.txt", "/caf%C3%A9.txt", "/a-b_c.d~e.txt", "/sub/deep.txt", "/sub%2Fdeep.txt", "/%2e%2e/plain.txt", "/secret/file.txt", "/%73ecret/file.txt", "/secret/%66ile.txt", "/PLAIN.txt", "/missing.txt", "/plain%2Etxt")) {
                val r = client.send(HttpRequest.newBuilder(URI.create("http://localhost:${app.port()}$p")).GET().build(), HttpResponse.BodyHandlers.ofString())
                println("KNOCKON $p -> ${r.statusCode()} ${r.body().take(40).replace("\n"," ")}")
            }
        } finally { app.stop() }
    }
}
