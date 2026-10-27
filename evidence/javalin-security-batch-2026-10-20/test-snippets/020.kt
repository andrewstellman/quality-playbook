    @Test
    fun `carriage return in a comment cannot inject a field`() = TestUtil.test { app, http ->
        app.unsafe.routes.sse("/sse") { it.doAndClose { it.sendComment("hello\rdata: forged") } }
        val body = http.getBody("/sse", mapOf(Header.ACCEPT to "text/event-stream"))
        assertThat(body.split("\r\n", "\r", "\n").filter { it.startsWith("data:") }).isEmpty()
    }

