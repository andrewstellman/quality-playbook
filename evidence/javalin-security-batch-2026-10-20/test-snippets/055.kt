    @Test
    fun `before-handler cannot be bypassed with an alias of a static file path`() = testStaticFiles(defaultStaticResourceApp) { app, http ->
        app.unsafe.routes.before("/protected/*") { throw UnauthorizedResponse("Protected") }
        assertThat(http.get("/protected/secret.html").httpCode()).isEqualTo(UNAUTHORIZED)
        // routing matches the raw path, so neither alias matches "/protected/*", but Jetty resolved both to protected/secret.html
        for (alias in listOf("/%70rotected/secret.html", "//protected/secret.html")) {
            val response = http.get(alias)
            assertThat(response.httpCode()).isEqualTo(NOT_FOUND)
            assertThat(response.body).doesNotContain("Secret file")
        }
    }

