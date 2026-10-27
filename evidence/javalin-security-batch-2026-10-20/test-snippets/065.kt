    @Test
    fun `basicAuthCredentials accepts the scheme name in any case`() = TestUtil.test { app, http ->
        app.unsafe.routes.get("/") { ctx -> ctx.result(ctx.basicAuthCredentials()?.username ?: "null") }
        val token = Base64.getEncoder().encodeToString("some-username:some-password".toByteArray())
        assertThat(http.getBody("/", mapOf(Header.AUTHORIZATION to "basic $token"))).isEqualTo("some-username")
        assertThat(http.getBody("/", mapOf(Header.AUTHORIZATION to "BASIC $token"))).isEqualTo("some-username")
    }

