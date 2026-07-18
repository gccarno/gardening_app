package com.gardenapp.core.notifications.evaluators

import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.NotificationEvent
import com.gardenapp.core.notifications.NotificationType
import javax.inject.Inject

/**
 * Time-of-year planting suggestions, reusing the dashboard's seasonal hint
 * (season + hint_text + hint_crops, computed server-side from frost dates and
 * USDA zone — same content as SeasonalHintCard on the dashboard).
 */
class PlantingSuggestionEvaluator @Inject constructor(private val api: ApiService) {

    suspend fun evaluate(garden: Garden): NotificationEvent? {
        val dashboard = try {
            api.getDashboard(garden.id)
        } catch (e: Exception) {
            return null
        }
        if (dashboard.hintText.isBlank()) return null

        val message = buildString {
            append(dashboard.hintText.trim())
            if (!endsWith(".") && !endsWith("!")) append(".")
            if (dashboard.hintCrops.isNotBlank()) {
                append(" Try: ${dashboard.hintCrops.trim()}.")
            }
        }
        val season = dashboard.season.ifBlank { "Seasonal" }
        return NotificationEvent(
            type = NotificationType.PLANTING,
            gardenId = garden.id,
            title = "$season planting — ${garden.name}",
            message = message,
        )
    }
}
