package com.gardenapp.core.notifications

import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.Plant
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.evaluators.GrowthEvaluator
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class GrowthEvaluatorTest {

    private val api = mockk<ApiService>()
    private val evaluator = GrowthEvaluator(api)
    private val garden = Garden(id = 7, name = "Back Yard")
    private val today = LocalDate.of(2026, 7, 16)

    private fun plant(
        name: String = "Tomato",
        plantedDate: String? = null,
        daysToGermination: Int? = null,
        daysToHarvest: Int? = null,
        expectedHarvest: String? = null,
        status: String? = "growing",
    ) = Plant(
        id = 1, name = name, gardenId = 7, plantedDate = plantedDate,
        daysToGermination = daysToGermination, daysToHarvest = daysToHarvest,
        expectedHarvest = expectedHarvest, status = status,
    )

    @Test
    fun `germination due today produces event`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } returns listOf(
            plant(name = "Basil", plantedDate = "2026-07-09", daysToGermination = 7)
        )
        val event = evaluator.evaluate(garden, frequencyDays = 1, today = today)!!
        assertEquals(NotificationType.GROWTH, event.type)
        assertTrue(event.message.contains("Basil should be germinating"))
    }

    @Test
    fun `expected harvest inside frequency window produces event`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } returns listOf(
            plant(expectedHarvest = "2026-07-14")
        )
        val event = evaluator.evaluate(garden, frequencyDays = 3, today = today)!!
        assertTrue(event.message.contains("Tomato may be ready to harvest"))
    }

    @Test
    fun `harvest computed from planted date plus days to harvest`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } returns listOf(
            plant(plantedDate = "2026-05-07", daysToHarvest = 70)
        )
        val event = evaluator.evaluate(garden, frequencyDays = 1, today = today)!!
        assertTrue(event.message.contains("ready to harvest"))
    }

    @Test
    fun `milestones outside the window are silent`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } returns listOf(
            plant(plantedDate = "2026-07-01", daysToGermination = 7),   // 8 days ago
            plant(expectedHarvest = "2026-07-20"),                       // future
        )
        assertNull(evaluator.evaluate(garden, frequencyDays = 1, today = today))
    }

    @Test
    fun `finished plants are ignored`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } returns listOf(
            plant(expectedHarvest = "2026-07-16", status = "harvested")
        )
        assertNull(evaluator.evaluate(garden, frequencyDays = 1, today = today))
    }

    @Test
    fun `missing dates are silent`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } returns listOf(plant())
        assertNull(evaluator.evaluate(garden, frequencyDays = 1, today = today))
    }

    @Test
    fun `network failure is silent`() = runTest {
        coEvery { api.getPlants(gardenId = 7) } throws java.io.IOException("timeout")
        assertNull(evaluator.evaluate(garden, frequencyDays = 1, today = today))
    }
}
