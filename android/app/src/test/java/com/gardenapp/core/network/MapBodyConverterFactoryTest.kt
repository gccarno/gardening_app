package com.gardenapp.core.network

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit

/**
 * Guards the Retrofit wiring for `Map<String, Any?>` bodies. Without
 * [MapBodyConverterFactory] every write endpoint in [ApiService] — 41 of them,
 * including createBed, placePlantInGrid and updateBedPlantCare — throws
 * "Unable to create @Body converter" at call time.
 */
class MapBodyConverterFactoryTest {

    private lateinit var server: MockWebServer
    private lateinit var api: ApiService

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        val json = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }
        api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MapBodyConverterFactory())
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ApiService::class.java)
    }

    @After
    fun tearDown() = server.shutdown()

    @Test
    fun `care body serializes instead of failing to build a converter`() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"ok":true}"""))

        api.updateBedPlantCare(
            42,
            mapOf(
                "last_watered" to "2026-08-09",
                "stage" to "harvesting",
                "health_notes" to "fine",
            ),
        )

        val body = JSONObject(server.takeRequest().body.readUtf8())
        assertEquals("2026-08-09", body.getString("last_watered"))
        assertEquals("harvesting", body.getString("stage"))
        assertEquals("fine", body.getString("health_notes"))
    }

    @Test
    fun `mixed value types survive the round trip`() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"id":1,"name":"B","garden_id":3}"""))

        api.createBed(
            mapOf(
                "name" to "Bed",
                "garden_id" to 3,
                "width_ft" to 4.5f,
                "soil_ph" to 6.5,
            ),
        )

        val body = JSONObject(server.takeRequest().body.readUtf8())
        assertEquals("Bed", body.getString("name"))
        assertEquals(3, body.getInt("garden_id"))
        assertEquals(4.5, body.getDouble("width_ft"), 0.001)
        assertEquals(6.5, body.getDouble("soil_ph"), 0.001)
    }

    @Test
    fun `an explicit null is sent so the server clears the field`() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"ok":true}"""))

        api.updateBedPlantCare(7, mapOf("last_harvest" to null))

        val raw = server.takeRequest().body.readUtf8()
        assertTrue("expected an explicit null, got: $raw", JSONObject(raw).isNull("last_harvest"))
    }

    @Test
    fun `nested lists of maps serialize for bulk placement`() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"ok":true}"""))

        api.placePlantsBulk(
            3,
            mapOf(
                "library_id" to 12,
                "positions" to listOf(
                    mapOf("grid_x" to 0, "grid_y" to 0),
                    mapOf("grid_x" to 12, "grid_y" to 0),
                ),
            ),
        )

        val body = JSONObject(server.takeRequest().body.readUtf8())
        val positions = body.getJSONArray("positions")
        assertEquals(2, positions.length())
        assertEquals(12, positions.getJSONObject(1).getInt("grid_x"))
    }
}
