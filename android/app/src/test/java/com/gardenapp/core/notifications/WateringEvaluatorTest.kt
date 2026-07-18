package com.gardenapp.core.notifications

import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.evaluators.WateringEvaluator
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class WateringEvaluatorTest {

    private val api = mockk<ApiService>()
    private val evaluator = WateringEvaluator(api)
    private val garden = Garden(id = 7, name = "Back Yard")

    private fun status(beds: String, hasData: Boolean = true) = Json.parseToJsonElement(
        """{"garden_id":7,"date":"2026-07-16","has_weather_data":$hasData,
            "forecast_today":null,"beds":[$beds]}"""
    )

    @Test
    fun `urgent bed produces high-priority event`() = runTest {
        coEvery { api.getWateringStatus(7) } returns status(
            """{"bed_id":1,"bed_name":"Tomato Bed","urgency_score":82,"label":"urgent"},
               {"bed_id":2,"bed_name":"Herbs","urgency_score":55,"label":"water_today"},
               {"bed_id":3,"bed_name":"Lettuce","urgency_score":10,"label":"ok"}"""
        )
        val event = evaluator.evaluate(garden)!!
        assertEquals(NotificationType.WATERING, event.type)
        assertEquals(7, event.gardenId)
        assertTrue(event.highPriority)
        assertTrue(event.message.contains("2 beds"))
        assertTrue(event.message.contains("Tomato Bed"))
    }

    @Test
    fun `single bed message names the bed without a count`() = runTest {
        coEvery { api.getWateringStatus(7) } returns status(
            """{"bed_id":2,"bed_name":"Herbs","urgency_score":60,"label":"water_today"}"""
        )
        val event = evaluator.evaluate(garden)!!
        assertFalse(event.highPriority)
        assertTrue(event.message.startsWith("Herbs needs water"))
    }

    @Test
    fun `recent rain keeps urgency low and stays silent`() = runTest {
        coEvery { api.getWateringStatus(7) } returns status(
            """{"bed_id":1,"bed_name":"Tomato Bed","urgency_score":12,"label":"ok"},
               {"bed_id":2,"bed_name":"Herbs","urgency_score":30,"label":"consider"}"""
        )
        assertNull(evaluator.evaluate(garden))
    }

    @Test
    fun `no weather data is silent`() = runTest {
        coEvery { api.getWateringStatus(7) } returns status(
            """{"bed_id":1,"bed_name":"Tomato Bed","urgency_score":90,"label":"urgent"}""",
            hasData = false,
        )
        assertNull(evaluator.evaluate(garden))
    }

    @Test
    fun `network failure is silent`() = runTest {
        coEvery { api.getWateringStatus(7) } throws java.io.IOException("timeout")
        assertNull(evaluator.evaluate(garden))
    }
}
