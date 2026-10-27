    @Test
    fun `basic auth filter plugin denies every request when no credentials are configured`() {
        val basicAuthApp = Javalin.create { cfg ->
            cfg.registerPlugin(BasicAuthPlugin { })
            cfg.routes.get("/hellopath") { it.result("Hello") }
        }
        TestUtil.test(basicAuthApp) { _, http ->
            assertThat(http.get("/hellopath").httpCode()).isEqualTo(HttpStatus.UNAUTHORIZED)
            Unirest.get("${http.origin}/hellopath").basicAuth("", "").asString().let { assertThat(it.httpCode()).isEqualTo(HttpStatus.UNAUTHORIZED) }
        }
    }

