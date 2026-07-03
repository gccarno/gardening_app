package com.gardenapp.core.network

/**
 * In-memory holder for the current bearer token, mirroring the
 * [ServerConfig] pattern. Persisted value lives in DataStore
 * (AUTH_TOKEN_KEY) and is pushed here on app start / login / logout.
 */
object AuthConfig {
    @Volatile
    var token: String? = null
}
