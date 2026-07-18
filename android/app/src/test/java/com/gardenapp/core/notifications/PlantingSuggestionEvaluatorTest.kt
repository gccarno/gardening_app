package com.gardenapp.core.notifications

import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.DashboardMetrics
import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.evaluators.PlantingSuggestionEvaluator
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlantingSuggestionEvaluatorTest {

    private val api = mockk<ApiService>()
    private val evaluator = PlantingSuggestionEvaluator(api)
    private val garden = Garden(id = 7, name = "Back Yard")

    private fun dashboard(season: String = "", hintText: String = "", hintCrops: String = "") =
        DashboardData(
            metrics = DashboardMetrics(),
            season = season, hintText = hintText, hintCrops = hintCrops,
        )

    @Test
    fun `seasonal hint produces event with crops`() = runTest {
        coEvery { api.getDashboard(7) } returns dashboard(
            season = "Summer",
            hintText = "Direct-sow fall brassicas now",
            hintCrops = "kale, cabbage, broccoli",
        )
        val event = evaluator.evaluate(garden)!!
        assertEquals(NotificationType.PLANTING, event.type)
        assertTrue(event.title.contains("Summer"))
        assertTrue(event.message.contains("Direct-sow fall brassicas now"))
        assertTrue(event.message.contains("kale, cabbage, broccoli"))
    }

    @Test
    fun `blank hint is silent`() = runTest {
        coEvery { api.getDashboard(7) } returns dashboard(season = "Winter")
        assertNull(evaluator.evaluate(garden))
    }

    @Test
    fun `network failure is silent`() = runTest {
        coEvery { api.getDashboard(7) } throws java.io.IOException("timeout")
        assertNull(evaluator.evaluate(garden))
    }
}
