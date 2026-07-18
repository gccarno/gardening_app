package com.gardenapp.core.notifications.evaluators

import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.NotificationEvent
import com.gardenapp.core.notifications.NotificationType
import java.time.LocalDate
import javax.inject.Inject

/**
 * Growth-tracking milestones: expected germination (planted_date +
 * days_to_germination) and expected harvest (expected_harvest, else
 * planted_date + days_to_harvest). A milestone fires when it falls within the
 * last [frequencyDays] days, so a periodic check catches it once; the
 * lastNotified gate in the worker prevents repeats.
 */
class GrowthEvaluator @Inject constructor(private val api: ApiService) {

    suspend fun evaluate(garden: Garden, frequencyDays: Int, today: LocalDate): NotificationEvent? {
        val plants = try {
            api.getPlants(gardenId = garden.id)
        } catch (e: Exception) {
            return null
        }
        val window = frequencyDays.toLong().coerceAtLeast(1)
        val milestones = mutableListOf<String>()
        for (p in plants) {
            if (p.status in FINISHED_STATUSES) continue
            val planted = p.plantedDate.toLocalDateOrNull()
            if (planted != null) {
                p.daysToGermination?.let { days ->
                    val due = planted.plusDays(days.toLong())
                    if (due.isWithin(today, window)) {
                        milestones += "${p.name} should be germinating"
                    }
                }
            }
            val harvest = p.expectedHarvest.toLocalDateOrNull()
                ?: p.daysToHarvest?.let { planted?.plusDays(it.toLong()) }
            if (harvest != null && harvest.isWithin(today, window)) {
                milestones += "${p.name} may be ready to harvest"
            }
        }
        if (milestones.isEmpty()) return null

        val message = milestones.take(MAX_LISTED).joinToString(". ") +
            (if (milestones.size > MAX_LISTED) {
                " — and ${milestones.size - MAX_LISTED} more."
            } else ".")
        return NotificationEvent(
            type = NotificationType.GROWTH,
            gardenId = garden.id,
            title = "Growth update — ${garden.name}",
            message = message,
        )
    }

    private fun String?.toLocalDateOrNull(): LocalDate? =
        this?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }

    private fun LocalDate.isWithin(today: LocalDate, days: Long): Boolean =
        !isAfter(today) && !isBefore(today.minusDays(days))

    companion object {
        private val FINISHED_STATUSES = setOf("harvested", "removed", "dead")
        private const val MAX_LISTED = 3
    }
}
