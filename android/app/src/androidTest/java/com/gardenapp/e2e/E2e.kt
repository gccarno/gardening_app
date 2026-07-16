package com.gardenapp.e2e

import android.util.Log
import androidx.datastore.preferences.core.edit
import androidx.test.platform.app.InstrumentationRegistry
import com.gardenapp.SERVER_URL_KEY
import com.gardenapp.core.dataStore
import com.gardenapp.core.network.AuthConfig
import com.gardenapp.core.network.ServerConfig
import com.gardenapp.feature.auth.AUTH_TOKEN_KEY
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * Shared state + API client for the instrumented E2E suite against the live
 * backend. Configuration arrives as instrumentation args (fed from the repo
 * .env by scripts/run_e2e.ps1 — never hardcoded):
 *
 *   -e E2E_BASE_URL https://…   -e E2E_EMAIL you@x.com   -e E2E_PASSWORD …
 *   -e E2E_SYNC_GARDEN_ID 123   (only for SyncVerifyAndMutateTest)
 *
 * Every entity it creates is named "[E2E] <runId> …" and logged to logcat
 * under the E2E_MANIFEST tag; the orchestrator pulls that into the run
 * manifest so a failed teardown can be traced in Neon.
 */
object E2e {
    const val PREFIX = "[E2E]"
    private const val MANIFEST_TAG = "E2E_MANIFEST"

    private val args get() = InstrumentationRegistry.getArguments()
    val baseUrl: String get() = (args.getString("E2E_BASE_URL") ?: ServerConfig.DEFAULT_BASE_URL).trimEnd('/')
    val email: String? get() = args.getString("E2E_EMAIL")
    val password: String? get() = args.getString("E2E_PASSWORD")
    val syncGardenId: Int? get() = args.getString("E2E_SYNC_GARDEN_ID")?.toIntOrNull()

    val runId: String by lazy {
        "e2e-android-" + SimpleDateFormat("yyyyMMddHHmmss", Locale.US).format(Date())
    }

    // Cross-class state within one instrumentation run (classes run in
    // alphabetical order in a single process).
    var gardenId: Int? = null
    var bedId: Int? = null
    var plantId: Int? = null

    fun testName(label: String) = "$PREFIX $runId $label"

    private val http = OkHttpClient.Builder()
        .connectTimeout(120, TimeUnit.SECONDS)  // Render cold start
        .readTimeout(120, TimeUnit.SECONDS)
        .build()
    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private var token: String? = null

    fun logManifest(entry: Map<String, Any?>) {
        Log.i(MANIFEST_TAG, JSONObject(entry + mapOf("runId" to runId, "platform" to "android")).toString())
    }

    /** Log in over HTTP (also warms the Render service through a cold start). */
    fun login(): String {
        token?.let { return it }
        val em = email ?: error("E2E_EMAIL instrumentation arg missing")
        val pw = password ?: error("E2E_PASSWORD instrumentation arg missing")
        val body = JSONObject(mapOf("email" to em, "password" to pw)).toString().toRequestBody(jsonType)
        http.newCall(Request.Builder().url("$baseUrl/api/auth/login").post(body).build()).execute().use { resp ->
            check(resp.isSuccessful) { "login failed: ${resp.code}" }
            val t = JSONObject(resp.body!!.string()).getString("token")
            token = t
            return t
        }
    }

    /** Seed DataStore so the app under test starts signed in at [baseUrl]. */
    fun ensureSignedIn() {
        val t = login()
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        runBlocking {
            ctx.dataStore.edit { prefs ->
                prefs[SERVER_URL_KEY] = baseUrl
                prefs[AUTH_TOKEN_KEY] = t
            }
        }
        ServerConfig.baseUrl = baseUrl
        AuthConfig.token = t
    }

    fun signOutLocally() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        runBlocking { ctx.dataStore.edit { it.remove(AUTH_TOKEN_KEY) } }
        AuthConfig.token = null
    }

    // ── Minimal JSON API client for setup / verification / teardown ──────────
    private fun call(method: String, path: String, payload: JSONObject? = null): String {
        val builder = Request.Builder()
            .url("$baseUrl$path")
            .header("Authorization", "Bearer ${login()}")
        when (method) {
            "GET" -> builder.get()
            "DELETE" -> builder.delete()
            else -> builder.method(method, (payload ?: JSONObject()).toString().toRequestBody(jsonType))
        }
        http.newCall(builder.build()).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            check(resp.isSuccessful) { "$method $path -> ${resp.code}: $text" }
            if (method != "GET") {
                runCatching {
                    val id = JSONObject(text).optInt("id", -1)
                    if (id > 0) logManifest(mapOf("via" to "api", "method" to method, "path" to path, "id" to id))
                }
            }
            return text
        }
    }

    fun getArray(path: String): JSONArray = JSONArray(call("GET", path))
    fun getObject(path: String): JSONObject = JSONObject(call("GET", path))
    fun post(path: String, payload: Map<String, Any?> = emptyMap()): JSONObject =
        JSONObject(call("POST", path, JSONObject(payload)).ifBlank { "{}" })
    fun put(path: String, payload: Map<String, Any?>): JSONObject =
        JSONObject(call("PUT", path, JSONObject(payload)).ifBlank { "{}" })
    fun delete(path: String) { call("DELETE", path) }
}
