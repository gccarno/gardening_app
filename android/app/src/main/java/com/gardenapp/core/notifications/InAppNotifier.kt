package com.gardenapp.core.notifications

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * In-app "toast" channel: MainActivity collects [events] and shows a snackbar.
 * Only emits while the app is foregrounded — background events reach the user
 * as system notifications instead.
 */
@Singleton
class InAppNotifier @Inject constructor() {
    private val _events = MutableSharedFlow<NotificationEvent>(extraBufferCapacity = 8)
    val events: SharedFlow<NotificationEvent> = _events.asSharedFlow()

    @Volatile
    var isForeground: Boolean = false

    fun tryEmit(event: NotificationEvent): Boolean =
        isForeground && _events.tryEmit(event)
}
