package com.gardenapp.core.notifications

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.gardenapp.R
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Delivers a [NotificationEvent] both ways: a system notification (works with
 * the app closed) and the in-app snackbar flow (when foregrounded).
 */
@Singleton
class GardenNotifier @Inject constructor(
    @ApplicationContext private val context: Context,
    private val inAppNotifier: InAppNotifier,
) {
    fun notify(event: NotificationEvent) {
        postSystemNotification(event)
        inAppNotifier.tryEmit(event)
    }

    private fun postSystemNotification(event: NotificationEvent) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        // Tapping opens the garden via the existing gardenapp://garden deep link.
        val tapIntent = PendingIntent.getActivity(
            context,
            event.gardenId,
            Intent(Intent.ACTION_VIEW, Uri.parse("gardenapp://garden/${event.gardenId}"))
                .setPackage(context.packageName),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, event.type.channelId)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(event.title)
            .setContentText(event.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(event.message))
            .setPriority(
                if (event.highPriority) NotificationCompat.PRIORITY_HIGH
                else NotificationCompat.PRIORITY_DEFAULT
            )
            .setContentIntent(tapIntent)
            .setAutoCancel(true)
            .build()
        // Stable ID per (type, garden): repeat reminders update instead of stacking.
        NotificationManagerCompat.from(context)
            .notify(event.type.ordinal * 10_000 + event.gardenId, notification)
    }
}
