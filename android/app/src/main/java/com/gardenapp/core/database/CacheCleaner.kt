package com.gardenapp.core.database

import androidx.room.withTransaction
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Drops everything that came from a server.
 *
 * Called on sign-out and when the server URL changes — prod and a LAN backend
 * reuse the same integer ids, so a mixed database would show garden "3" from the
 * wrong server.
 *
 * `notification_settings` is deliberately left alone: it is a device-local user
 * setting, not a cache, and nothing can restore it.
 */
@Singleton
class CacheCleaner @Inject constructor(
    private val db: GardenDatabase,
) {
    suspend fun clearAll() = db.withTransaction {
        db.gardenDao().deleteAll()
        db.bedDao().deleteAll()
        db.plantDao().deleteAll()
        db.taskDao().deleteAll()
        db.weatherDao().deleteAll()
        db.cacheDao().apply {
            clearDashboard()
            clearBedGrid()
            clearPlantDetail()
            clearMeta()
        }
    }
}
