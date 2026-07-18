package com.gardenapp.core.notifications

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.gardenapp.SERVER_URL_KEY
import com.gardenapp.core.dataStore
import com.gardenapp.core.database.dao.GardenDao
import com.gardenapp.core.database.dao.NotificationSettingsDao
import com.gardenapp.core.database.entities.toGarden
import com.gardenapp.core.network.AuthConfig
import com.gardenapp.core.network.ServerConfig
import com.gardenapp.core.notifications.evaluators.GrowthEvaluator
import com.gardenapp.core.notifications.evaluators.PlantingSuggestionEvaluator
import com.gardenapp.core.notifications.evaluators.WateringEvaluator
import com.gardenapp.feature.auth.AUTH_TOKEN_KEY
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.flow.first
import java.time.LocalDateTime

/**
 * Hourly periodic worker that evaluates every enabled per-garden notification
 * setting. Each (garden, type) row fires only when its hour-of-day and
 * frequency gate passes ([shouldNotify]); per-row failures are isolated.
 */
@HiltWorker
class GardenNotificationWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val settingsDao: NotificationSettingsDao,
    private val gardenDao: GardenDao,
    private val wateringEvaluator: WateringEvaluator,
    private val growthEvaluator: GrowthEvaluator,
    private val plantingEvaluator: PlantingSuggestionEvaluator,
    private val notifier: GardenNotifier,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        // Headless start: MainActivity normally hydrates these singletons from
        // DataStore; the worker must do it itself before any Retrofit call.
        val prefs = applicationContext.dataStore.data.first()
        val token = prefs[AUTH_TOKEN_KEY] ?: return Result.success() // signed out
        prefs[SERVER_URL_KEY]?.let { ServerConfig.baseUrl = it }
        AuthConfig.token = token

        val enabled = settingsDao.getEnabled()
        if (enabled.isEmpty()) return Result.success()

        val gardens = gardenDao.getAllGardens().first()
            .associate { it.id to it.toGarden() }
        val now = LocalDateTime.now()
        val today = now.toLocalDate()

        for (setting in enabled) {
            val garden = gardens[setting.gardenId] ?: continue
            if (!shouldNotify(now.hour, setting.hourOfDay, today.toEpochDay(),
                    setting.lastNotifiedEpochDay, setting.frequencyDays)
            ) {
                continue
            }
            val event = try {
                when (NotificationType.valueOf(setting.type)) {
                    NotificationType.WATERING ->
                        wateringEvaluator.evaluate(garden)
                    NotificationType.GROWTH ->
                        growthEvaluator.evaluate(garden, setting.frequencyDays, today)
                    NotificationType.PLANTING ->
                        plantingEvaluator.evaluate(garden)
                }
            } catch (e: Exception) {
                Log.w(TAG, "evaluator ${setting.type} failed for garden ${garden.id}", e)
                null
            }
            if (event != null) {
                notifier.notify(event)
                settingsDao.updateLastNotified(
                    setting.gardenId, setting.type, today.toEpochDay())
            }
        }
        return Result.success()
    }

    companion object {
        private const val TAG = "GardenNotificationWorker"
        const val UNIQUE_WORK_NAME = "garden_notifications"
    }
}
