package com.gardenapp.core.database.dao

import androidx.room.*
import com.gardenapp.core.database.entities.NotificationSettingsEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface NotificationSettingsDao {
    @Query("SELECT * FROM notification_settings WHERE enabled = 1")
    suspend fun getEnabled(): List<NotificationSettingsEntity>

    @Query("SELECT * FROM notification_settings WHERE gardenId = :gardenId")
    fun observeForGarden(gardenId: Int): Flow<List<NotificationSettingsEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(settings: NotificationSettingsEntity)

    @Query(
        "UPDATE notification_settings SET lastNotifiedEpochDay = :epochDay " +
            "WHERE gardenId = :gardenId AND type = :type"
    )
    suspend fun updateLastNotified(gardenId: Int, type: String, epochDay: Long)

    @Query("DELETE FROM notification_settings WHERE gardenId = :gardenId")
    suspend fun deleteForGarden(gardenId: Int)
}
