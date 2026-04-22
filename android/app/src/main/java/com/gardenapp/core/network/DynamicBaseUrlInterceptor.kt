package com.gardenapp.core.network

import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Rewrites the request host/scheme/port from the current ServerConfig.baseUrl at call time,
 * so changing the server URL in Settings takes effect without rebuilding Retrofit.
 */
class DynamicBaseUrlInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val baseUrl = ServerConfig.apiBaseUrl.toHttpUrl()
        val original = chain.request()
        val newUrl = original.url.newBuilder()
            .scheme(baseUrl.scheme)
            .host(baseUrl.host)
            .port(baseUrl.port)
            .build()
        return chain.proceed(original.newBuilder().url(newUrl).build())
    }
}
