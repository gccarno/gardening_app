package com.gardenapp.core.network

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class AuthInterceptorTest {

    private lateinit var server: MockWebServer
    private lateinit var client: OkHttpClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor())
            .build()
    }

    @After
    fun tearDown() {
        AuthConfig.token = null
        server.shutdown()
    }

    private fun request(): Request = Request.Builder().url(server.url("/api/gardens")).build()

    @Test
    fun `no header when logged out`() {
        AuthConfig.token = null
        server.enqueue(MockResponse().setBody("[]"))
        client.newCall(request()).execute().close()
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test
    fun `bearer header when logged in`() {
        AuthConfig.token = "tok123"
        server.enqueue(MockResponse().setBody("[]"))
        client.newCall(request()).execute().close()
        assertEquals("Bearer tok123", server.takeRequest().getHeader("Authorization"))
    }

    @Test
    fun `blank token sends no header`() {
        AuthConfig.token = ""
        server.enqueue(MockResponse().setBody("[]"))
        client.newCall(request()).execute().close()
        assertNull(server.takeRequest().getHeader("Authorization"))
    }
}
