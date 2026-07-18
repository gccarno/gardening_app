package com.gardenapp.core.notifications

enum class NotificationType(val channelId: String, val channelName: String) {
    WATERING("watering_reminders", "Watering reminders"),
    GROWTH("growth_milestones", "Growth milestones"),
    PLANTING("planting_suggestions", "Planting suggestions"),
}

data class NotificationEvent(
    val type: NotificationType,
    val gardenId: Int,
    val title: String,
    val message: String,
    val highPriority: Boolean = false,
)
