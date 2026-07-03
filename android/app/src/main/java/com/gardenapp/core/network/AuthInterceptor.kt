package com.gardenapp.core.network

import okhttp3.Interceptor
import okhttp3.Response

/** Adds `Authorization: Bearer <token>` to every request when logged in. */
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = AuthConfig.token
        val request = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        }
        return chain.proceed(request)
    }
}
