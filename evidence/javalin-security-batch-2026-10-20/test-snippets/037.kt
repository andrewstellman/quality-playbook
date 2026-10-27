    @Test
    fun `basic auth plugin protects websocket upgrades`() = TestUtil.test(Javalin.create { it.bundledPlugins.enableBasicAuth("u", "p") }) { app, http ->
        val log = ConcurrentLinkedQueue<String>()
        app.unsafe.routes.ws("/ws") { ws -> ws.onConnect { log.add("connected") } }
        val denied = http.wsUpgradeRequest("/ws")
        assertThat(denied.status).isEqualTo(HttpStatus.UNAUTHORIZED.code)
        assertThat(denied.headers.getFirst(Header.WWW_AUTHENTICATE)).isEqualTo("Basic")
        val token = java.util.Base64.getEncoder().encodeToString("u:p".toByteArray())
        val authorized = Unirest.get("${http.origin}/ws").header(Header.SEC_WEBSOCKET_KEY, "not-null").header(Header.SEC_WEBSOCKET_VERSION, "13").header(Header.AUTHORIZATION, "Basic $token").asString()
        assertThat(authorized.status).isNotEqualTo(HttpStatus.UNAUTHORIZED.code)
        assertThat(log).isEmpty()
    }

