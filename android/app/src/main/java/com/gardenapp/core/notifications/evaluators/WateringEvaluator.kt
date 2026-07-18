package com.gardenapp.core.notifications.evaluators

import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.NotificationEvent
import com.gardenapp.core.notifications.NotificationType
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

/**
 * Rain-aware watering reminders. The decision is delegated to the backend
 * watering engine (GET gardens/{id}/watering-status), which folds 14 days of
 * rainfall and today's forecast into a 0-100 urgency score per bed — heavy
 * recent rain yields low urgency, so no notification. Never notifies without
 * weather data or on network failure.
 */
class WateringEvaluator @Inject constructor(private val api: ApiService) {

    suspend fun evaluate(garden: Garden): NotificationEvent? {
        val status = try {
            api.getWateringStatus(garden.id)
        } catch (e: Exception) {
            return null
        }
        val obj = status as? JsonObject ?: return null
        if (obj["has_weather_data"]?.jsonPrimitive?.booleanOrNull != true) return null

        val beds = (obj["beds"] as? JsonArray ?: return null).mapNotNull { el ->
            val bed = el as? JsonObject ?: return@mapNotNull null
            val score = bed["urgency_score"]?.jsonPrimitive?.intOrNull
                ?: return@mapNotNull null
            val name = bed["bed_name"]?.jsonPrimitive?.contentOrNull ?: "A bed"
            name to score
        }
        val needingWater = beds.filter { (_, score) -> score >= NOTIFY_THRESHOLD }
        if (needingWater.isEmpty()) return null

        val (topName, topScore) = needingWater.maxBy { it.second }
        val message = if (needingWater.size == 1) {
            "$topName needs water (urgency $topScore/100)."
        } else {
            "${needingWater.size} beds need water — $topName is most urgent " +
                "($topScore/100)."
        }
        return NotificationEvent(
            type = NotificationType.WATERING,
            gardenId = garden.id,
            title = "Watering needed in ${garden.name}",
            message = message,
            highPriority = topScore >= URGENT_THRESHOLD,
        )
    }

    companion object {
        const val NOTIFY_THRESHOLD = 50   // engine label "water_today"
        const val URGENT_THRESHOLD = 75   // engine label "urgent"
    }
}
