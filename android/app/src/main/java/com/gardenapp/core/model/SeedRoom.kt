package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SeedTray(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("library_id") val libraryId: Int? = null,
    @SerialName("plant_name") val plantName: String,
    @SerialName("slot_number") val slotNumber: Int,
    @SerialName("sow_date") val sowDate: String? = null,
    @SerialName("germination_date") val germinationDate: String? = null,
    @SerialName("transplant_ready_date") val transplantReadyDate: String? = null,
    val stage: String,
    val notes: String? = null,
    @SerialName("image_url") val imageUrl: String? = null,
)
