package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Garden(
    val id: Int,
    val name: String,
    val description: String? = null,
    val unit: String = "ft",
    @SerialName("zip_code") val zipCode: String? = null,
    val city: String? = null,
    val state: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("usda_zone") val usdaZone: String? = null,
    @SerialName("zone_temp_range") val zoneTempRange: String? = null,
    @SerialName("last_frost_date") val lastFrostDate: String? = null,
    @SerialName("first_frost_date") val firstFrostDate: String? = null,
    @SerialName("watering_frequency_days") val wateringFrequencyDays: Int? = null,
    @SerialName("water_source") val waterSource: String? = null,
    @SerialName("background_image") val backgroundImage: String? = null,
    @SerialName("background_color") val backgroundColor: String? = null,
    @SerialName("background_pattern") val backgroundPattern: String? = null,
)

@Serializable
data class DashboardData(
    val metrics: DashboardMetrics,
    @SerialName("upcoming_tasks") val upcomingTasks: List<DashboardTask> = emptyList(),
    @SerialName("recent_plants") val recentPlants: List<DashboardPlant> = emptyList(),
    @SerialName("recent_activity") val recentActivity: List<DashboardActivity> = emptyList(),
    val season: String = "",
    @SerialName("season_icon") val seasonIcon: String = "",
    @SerialName("hint_action") val hintAction: String = "",
    @SerialName("hint_text") val hintText: String = "",
    @SerialName("hint_crops") val hintCrops: String = "",
    @SerialName("frost_context") val frostContext: String? = null,
)

@Serializable
data class DashboardMetrics(
    @SerialName("bed_count") val bedCount: Int = 0,
    @SerialName("plant_count") val plantCount: Int = 0,
    @SerialName("plants_active") val plantsActive: Int = 0,
    @SerialName("task_count") val taskCount: Int = 0,
    @SerialName("overdue_tasks") val overdueTasks: Int = 0,
)

@Serializable
data class DashboardTask(
    val id: Int,
    val title: String,
    @SerialName("task_type") val taskType: String? = null,
    @SerialName("due_date") val dueDate: String? = null,
    @SerialName("plant_name") val plantName: String? = null,
)

@Serializable
data class DashboardPlant(
    val id: Int,
    val name: String,
    val type: String? = null,
    val status: String? = null,
)

@Serializable
data class DashboardActivity(
    val id: Int,
    val title: String,
    @SerialName("completed_date") val completedDate: String? = null,
)
