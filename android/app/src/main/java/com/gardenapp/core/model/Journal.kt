package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class JournalEntry(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("plant_id") val plantId: Int? = null,
    @SerialName("entry_date") val entryDate: String,
    val title: String,
    val body: String? = null,
    val tags: List<String> = emptyList(),
    @SerialName("image_filename") val imageFilename: String? = null,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class JournalPage(
    val total: Int,
    val page: Int,
    val entries: List<JournalEntry>,
)
