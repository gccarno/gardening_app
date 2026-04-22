package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CanvasPlant(
    val id: Int,
    @SerialName("pos_x") val posX: Float,
    @SerialName("pos_y") val posY: Float,
    @SerialName("radius_ft") val radiusFt: Float = 1f,
    val color: String? = null,
    @SerialName("display_mode") val displayMode: String? = null,
    @SerialName("library_id") val libraryId: Int? = null,
    @SerialName("plant_id") val plantId: Int? = null,
    val name: String = "",
    @SerialName("image_filename") val imageFilename: String? = null,
    @SerialName("scientific_name") val scientificName: String? = null,
    val sunlight: String? = null,
    val water: String? = null,
    @SerialName("spacing_in") val spacingIn: Float? = null,
    @SerialName("planted_date") val plantedDate: String? = null,
    @SerialName("last_watered") val lastWatered: String? = null,
    val label: String? = null,
)
