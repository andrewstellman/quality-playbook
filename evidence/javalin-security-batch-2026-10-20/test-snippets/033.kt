    @Test
    fun `message is html-escaped when the response is served as html`() = TestUtil.test { app, http ->
        app.unsafe.routes.get("/") { throw BadRequestResponse("bad name: " + it.queryParam("n")) }
        val response = http.htmlGet("/?n=%3Cscript%3Ealert(1)%3C%2Fscript%3E")
        assertThat(response.headers.getFirst(Header.CONTENT_TYPE)).isEqualTo(ContentType.HTML)
        assertThat(response.body).doesNotContain("<script>")
        assertThat(response.body).contains("&lt;script&gt;")
    }

