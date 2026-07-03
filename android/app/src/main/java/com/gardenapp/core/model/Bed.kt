package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Bed(
    val id: Int,
    val name: String,
    @SerialName("garden_id") val gardenId: Int? = null,
    @SerialName("garden_name") val gardenName: String? = null,
    @SerialName("width_ft") val widthFt: Float = 4f,
    @SerialName("height_ft") val heightFt: Float = 8f,
    @SerialName("depth_ft") val depthFt: Float? = null,
    val location: String? = null,
    val description: String? = null,
    @SerialName("soil_notes") val soilNotes: String? = null,
    @SerialName("soil_ph") val soilPh: Float? = null,
    @SerialName("clay_pct") val clayPct: Float? = null,
    @SerialName("compost_pct") val compostPct: Float? = null,
    @SerialName("sand_pct") val sandPct: Float? = null,
    @SerialName("pos_x") val posX: Float? = null,
    @SerialName("pos_y") val posY: Float? = null,
    @SerialName("plant_count") val plantCount: Int? = null,
)

@Serializable
data class GridPlant(
    val id: Int,
    @SerialName("grid_x") val gridX: Int,
    @SerialName("grid_y") val gridY: Int,
    @SerialName("plant_id") val plantId: Int,
    @SerialName("plant_name") val plantName: String,
    @SerialName("image_filename") val imageFilename: String? = null,
    @SerialName("spacing_in") val spacingIn: Float? = null,
)

@Serializable
data class BedGridResponse(
    val bed: Bed,
    val placed: List<GridPlant> = emptyList(),
)

@Serializable
data class BedPlantDetail(
    val id: Int,
    @SerialName("plant_id") val plantId: Int,
    @SerialName("plant_name") val plantName: String,
    @SerialName("scientific_name") val scientificName: String? = null,
    @SerialName("image_filename") val imageFilename: String? = null,
    val sunlight: String? = null,
    val water: String? = null,
    @SerialName("spacing_in") val spacingIn: Float? = null,
    @SerialName("days_to_harvest") val daysToHarvest: Int? = null,
    @SerialName("last_watered") val lastWatered: String? = null,
    @SerialName("last_fertilized") val lastFertilized: String? = null,
    @SerialName("health_notes") val healthNotes: String? = null,
    val stage: String? = null,
)

@Serializable
data class RotationFamily(
    val family: String,
    @SerialName("plant_name") val plantName: String,
)

@Serializable
data class RotationWarnings(
    @SerialName("bed_id") val bedId: Int,
    @SerialName("families_in_bed") val familiesInBed: List<RotationFamily> = emptyList(),
    @SerialName("candidate_family") val candidateFamily: String? = null,
    val conflict: Boolean = false,
    val warning: String? = null,
)

@Serializable
data class PlantObservation(
    val id: Int,
    @SerialName("bed_plant_id") val bedPlantId: Int,
    @SerialName("observation_date") val observationDate: String,
    @SerialName("observation_type") val observationType: String,
    val severity: Int = 3,
    val notes: String? = null,
)

@Serializable
data class HealthScore(
    @SerialName("bed_plant_id") val bedPlantId: Int,
    @SerialName("health_score") val healthScore: Int,
    val label: String,
)
