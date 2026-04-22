package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Task(
    val id: Int,
    val title: String,
    val description: String? = null,
    @SerialName("task_type") val taskType: String? = null,
    @SerialName("due_date") val dueDate: String? = null,
    val completed: Boolean = false,
    @SerialName("completed_date") val completedDate: String? = null,
    @SerialName("plant_id") val plantId: Int? = null,
    @SerialName("garden_id") val gardenId: Int? = null,
    @SerialName("bed_id") val bedId: Int? = null,
    @SerialName("plant_name") val plantName: String? = null,
    @SerialName("garden_name") val gardenName: String? = null,
    @SerialName("bed_name") val bedName: String? = null,
)

enum class TaskType(val value: String, val displayName: String, val color: Long) {
    SEEDING("seeding", "Seeding", 0xFF8BC34A),
    TRANSPLANTING("transplanting", "Transplanting", 0xFF4CAF50),
    WATERING("watering", "Watering", 0xFF2196F3),
    FERTILIZING("fertilizing", "Fertilizing", 0xFFFF9800),
    MULCHING("mulching", "Mulching", 0xFF795548),
    WEEDING("weeding", "Weeding", 0xFFE91E63),
    HARVEST("harvest", "Harvest", 0xFFFFEB3B),
    OTHER("other", "Other", 0xFF9E9E9E);

    companion object {
        fun from(value: String?): TaskType =
            entries.find { it.value == value } ?: OTHER
    }
}
