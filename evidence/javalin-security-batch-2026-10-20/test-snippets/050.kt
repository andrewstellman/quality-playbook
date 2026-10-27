    @Test
    fun `HEAD request answered by a GET handler has the GET handler's route roles`() = TestUtil.test { app, http ->
        app.unsafe.routes.beforeMatched { if (A in it.routeRoles()) throw UnauthorizedResponse() }
        app.unsafe.routes.get("/admin", { it.result("secret") }, A)
        assertThat(http.get("/admin").status).isEqualTo(401)
        assertThat(http.call(HttpMethod.HEAD, "/admin").status).isEqualTo(401)
    }

