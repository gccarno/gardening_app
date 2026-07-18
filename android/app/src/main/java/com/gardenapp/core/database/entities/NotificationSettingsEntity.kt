package com.gardenapp.core.database.entities

import androidx.room.Entity

/** Per-garden, per-type notification preferences. Device-local only —
 *  notifications are inherently per-device, so nothing syncs to the backend. */
@Entity(tableName = "notification_settings", primaryKeys = ["gardenId", "type"])
data class NotificationSettingsEntity(
    val gardenId: Int,
    val type: String,               // NotificationType.name: WATERING / GROWTH / PLANTING
    val enabled: Boolean = false,   // opt-in
    val frequencyDays: Int = 1,     // notify at most every N days
    val hourOfDay: Int = 8,         // earliest hour (0-23) to notify
    val lastNotifiedEpochDay: Long? = null,
)
