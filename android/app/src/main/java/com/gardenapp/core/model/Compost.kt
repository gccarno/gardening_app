package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CompostMaterial(
    val material: String,
    @SerialName("date_added") val dateAdded: String,
    @SerialName("quantity_lbs") val quantityLbs: Double? = null,
)

@Serializable
data class CompostBin(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    val name: String,
    @SerialName("started_date") val startedDate: String? = null,
    @SerialName("estimated_ready_date") val estimatedReadyDate: String? = null,
    val stage: String,
    val notes: String? = null,
    val materials: List<CompostMaterial> = emptyList(),
    @SerialName("created_at") val createdAt: String,
)
