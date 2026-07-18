package com.gardenapp.core.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationManagerCompat

object NotificationChannels {
    /** Idempotent — createNotificationChannel is a no-op for existing channels. */
    fun ensureChannels(context: Context) {
        val manager = NotificationManagerCompat.from(context)
        NotificationType.entries.forEach { type ->
            manager.createNotificationChannel(
                NotificationChannel(
                    type.channelId,
                    type.channelName,
                    NotificationManager.IMPORTANCE_DEFAULT,
                )
            )
        }
    }
}
