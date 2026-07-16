package com.gardenapp.core.network

object ServerConfig {
    /** Cloud backend on Render. Local dev: override via Server settings
     *  (emulator: http://10.0.2.2:8000, physical device: http://<PC-LAN-IP>:8000). */
    const val DEFAULT_BASE_URL = "https://garden-app-wa0b.onrender.com"

    @Volatile
    var baseUrl: String = DEFAULT_BASE_URL
        set(value) {
            field = value.trimEnd('/')
        }

    val apiBaseUrl: String
        get() = "$baseUrl/api/"
}
