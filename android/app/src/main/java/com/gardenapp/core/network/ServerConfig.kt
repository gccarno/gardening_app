package com.gardenapp.core.network

object ServerConfig {
    const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"

    @Volatile
    var baseUrl: String = DEFAULT_BASE_URL
        set(value) {
            field = value.trimEnd('/')
        }

    val apiBaseUrl: String
        get() = "$baseUrl/api/"
}
