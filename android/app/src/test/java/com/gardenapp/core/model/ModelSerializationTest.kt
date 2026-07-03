package com.gardenapp.core.model

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Contract-drift guard: canned backend JSON must keep decoding into the
 * app's models with the production Json configuration (NetworkModule).
 */
class ModelSerializationTest {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    @Test
    fun `garden decodes from backend shape`() {
        val payload = """
            {"id": 3, "name": "Backyard", "description": null, "unit": "ft",
             "zip_code": "60601", "city": "Chicago", "state": "IL",
             "latitude": 41.88, "longitude": -87.62, "usda_zone": "6a",
             "last_frost_date": "2026-04-20", "watering_frequency_days": 5,
             "some_future_field": true}
        """.trimIndent()
        val garden = json.decodeFromString<Garden>(payload)
        assertEquals("Backyard", garden.name)
        assertEquals("60601", garden.zipCode)
        assertEquals("6a", garden.usdaZone)
        assertEquals(5, garden.wateringFrequencyDays)
        assertNull(garden.description)
    }

    @Test
    fun `compost bin decodes with materials`() {
        val payload = """
            {"id": 1, "garden_id": 3, "name": "Main bin", "stage": "active",
             "started_date": "2026-06-01", "estimated_ready_date": "2026-09-14",
             "notes": null, "created_at": "2026-06-01T12:00:00",
             "materials": [{"material": "grass clippings",
                            "date_added": "2026-06-02", "quantity_lbs": 4.5}]}
        """.trimIndent()
        val bin = json.decodeFromString<CompostBin>(payload)
        assertEquals("active", bin.stage)
        assertEquals(1, bin.materials.size)
        assertEquals(4.5, bin.materials[0].quantityLbs!!, 0.0)
    }

    @Test
    fun `login response decodes`() {
        val payload = """
            {"token": "abc123", "user": {"id": 1, "email": "me@example.com",
             "display_name": null}}
        """.trimIndent()
        val response = json.decodeFromString<LoginResponse>(payload)
        assertEquals("abc123", response.token)
        assertEquals("me@example.com", response.user.email)
    }
}
