package com.gardenapp.feature.garden.notifications

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import android.content.Context
import com.gardenapp.core.database.dao.NotificationSettingsDao
import com.gardenapp.core.database.entities.NotificationSettingsEntity
import com.gardenapp.core.notifications.GardenNotificationWorker
import com.gardenapp.core.notifications.NotificationType
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class NotificationSettingsViewModel @Inject constructor(
    private val dao: NotificationSettingsDao,
    @ApplicationContext private val appContext: Context,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val gardenId: Int = checkNotNull(savedStateHandle["gardenId"])

    private fun defaults() = NotificationType.entries.associateWith {
        NotificationSettingsEntity(gardenId = gardenId, type = it.name)
    }

    /** One row per type; gardens without saved rows get opt-out defaults. */
    val settings: StateFlow<Map<NotificationType, NotificationSettingsEntity>> =
        dao.observeForGarden(gardenId)
            .map { rows ->
                NotificationType.entries.associateWith { type ->
                    rows.find { it.type == type.name }
                        ?: NotificationSettingsEntity(gardenId = gardenId, type = type.name)
                }
            }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), defaults())

    fun setEnabled(type: NotificationType, enabled: Boolean) = update(type) {
        it.copy(enabled = enabled)
    }

    fun setFrequency(type: NotificationType, days: Int) = update(type) {
        it.copy(frequencyDays = days)
    }

    fun setHour(type: NotificationType, hour: Int) = update(type) {
        it.copy(hourOfDay = hour)
    }

    private fun update(
        type: NotificationType,
        transform: (NotificationSettingsEntity) -> NotificationSettingsEntity,
    ) {
        val current = settings.value[type]
            ?: NotificationSettingsEntity(gardenId = gardenId, type = type.name)
        viewModelScope.launch { dao.upsert(transform(current)) }
    }

    /** Debug-only manual trigger: run the notification worker once, now. */
    fun testNow() {
        WorkManager.getInstance(appContext).enqueue(
            OneTimeWorkRequestBuilder<GardenNotificationWorker>().build()
        )
    }
}
