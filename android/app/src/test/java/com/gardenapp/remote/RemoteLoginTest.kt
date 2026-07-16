package com.gardenapp.remote

import com.gardenapp.core.network.ServerConfig
import java.io.File
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.BeforeClass
import org.junit.Test

/**
 * Live login tests against the deployed backend (Render by default —
 * ServerConfig.DEFAULT_BASE_URL). Credentials come from the repo-root .env
 * (USERNAME / PASSWORD keys), read from the file rather than the process
 * environment because Windows always defines USERNAME as the OS account name.
 * Skipped automatically when .env or the keys are missing (e.g. CI).
 *
 * Override the target server with the GARDEN_TEST_BASE_URL environment variable.
 */
class RemoteLoginTest {

    companion object {
        private val baseUrl: String =
            (System.getenv("GARDEN_TEST_BASE_URL") ?: ServerConfig.DEFAULT_BASE_URL).trimEnd('/')

        private val dotEnv: Map<String, String> by lazy {
            // Unit tests run with the module dir (android/app) as the working
            // directory; walk upward to find the repo-root .env.
            var dir: File? = File(System.getProperty("user.dir")).absoluteFile
            repeat(5) {
                val f = File(dir, ".env")
                if (f.isFile) {
                    return@lazy f.readLines().mapNotNull { line ->
                        val m = Regex("""^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*?)\s*$""").find(line)
                        m?.let { it.groupValues[1] to it.groupValues[2].trim('"', '\'') }
                    }.toMap()
                }
                dir = dir?.parentFile ?: return@lazy emptyMap()
            }
            emptyMap()
        }

        private val email: String? get() = dotEnv["USERNAME"]
        private val password: String? get() = dotEnv["PASSWORD"]

        private val client = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        private const val COLD_START_MS = 120_000L
        private var warmedUp = false

        @JvmStatic
        @BeforeClass
        fun warmUp() {
            if (dotEnv["USERNAME"].isNullOrBlank() || dotEnv["PASSWORD"].isNullOrBlank()) return
            // Render free tier spins down when idle; poll /api/health through
            // any cold start so the tests measure auth, not boot time.
            val deadline = System.currentTimeMillis() + COLD_START_MS
            while (System.currentTimeMillis() < deadline) {
                try {
                    client.newCall(Request.Builder().url("$baseUrl/api/health").build())
                        .execute().use { if (it.isSuccessful) { warmedUp = true; return } }
                } catch (_: Exception) {
                    // still booting / unreachable — retry
                }
                Thread.sleep(3000)
            }
        }
    }

    @Before
    fun requireCredentials() {
        assumeTrue(
            "Skipped: USERNAME/PASSWORD not set in repo-root .env",
            !email.isNullOrBlank() && !password.isNullOrBlank(),
        )
        assertTrue("$baseUrl/api/health not reachable within ${COLD_START_MS} ms", warmedUp)
    }

    private fun login(email: String, password: String) =
        client.newCall(
            Request.Builder()
                .url("$baseUrl/api/auth/login")
                .post(
                    """{"email":"$email","password":"$password"}"""
                        .toRequestBody("application/json".toMediaType()),
                )
                .build(),
        ).execute()

    @Test
    fun `login with env credentials returns token`() {
        login(email!!, password!!).use { res ->
            assertEquals(200, res.code)
            val body = Json.parseToJsonElement(res.body!!.string()).jsonObject
            assertTrue(body["token"]!!.jsonPrimitive.content.isNotBlank())
            assertEquals(email, body["user"]!!.jsonObject["email"]!!.jsonPrimitive.content)
        }
    }

    @Test
    fun `wrong password is rejected with 401`() {
        login(email!!, "definitely-wrong-password").use { res ->
            assertEquals(401, res.code)
        }
    }

    @Test
    fun `token authenticates against auth me`() {
        val token = login(email!!, password!!).use { res ->
            Json.parseToJsonElement(res.body!!.string())
                .jsonObject["token"]!!.jsonPrimitive.content
        }
        client.newCall(
            Request.Builder()
                .url("$baseUrl/api/auth/me")
                .header("Authorization", "Bearer $token")
                .build(),
        ).execute().use { res ->
            assertEquals(200, res.code)
            val body = Json.parseToJsonElement(res.body!!.string()).jsonObject
            assertEquals(email, body["email"]!!.jsonPrimitive.content)
        }
    }
}
