package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class LibraryListEntry(
    val id: Int,
    val name: String,
    val type: String? = null,
    @SerialName("spacing_in") val spacingIn: Float? = null,
    val sunlight: String? = null,
    val water: String? = null,
    @SerialName("days_to_germination") val daysToGermination: Int? = null,
    @SerialName("days_to_harvest") val daysToHarvest: Int? = null,
    @SerialName("image_filename") val imageFilename: String? = null,
    val difficulty: String? = null,
    @SerialName("min_zone") val minZone: Int? = null,
    @SerialName("max_zone") val maxZone: Int? = null,
)

@Serializable
data class LibraryListResponse(
    val total: Int,
    val page: Int,
    @SerialName("per_page") val perPage: Int,
    val pages: Int,
    val entries: List<LibraryListEntry>,
)

@Serializable
data class LibraryEntry(
    val id: Int,
    val name: String,
    @SerialName("scientific_name") val scientificName: String? = null,
    val type: String? = null,
    val sunlight: String? = null,
    val water: String? = null,
    @SerialName("spacing_in") val spacingIn: Float? = null,
    @SerialName("days_to_germination") val daysToGermination: Int? = null,
    @SerialName("days_to_harvest") val daysToHarvest: Int? = null,
    @SerialName("min_zone") val minZone: Int? = null,
    @SerialName("max_zone") val maxZone: Int? = null,
    @SerialName("temp_min_f") val tempMinF: Float? = null,
    @SerialName("temp_max_f") val tempMaxF: Float? = null,
    @SerialName("soil_ph_min") val soilPhMin: Float? = null,
    @SerialName("soil_ph_max") val soilPhMax: Float? = null,
    @SerialName("soil_type") val soilType: String? = null,
    val notes: String? = null,
    val family: String? = null,
    val layer: String? = null,
    @SerialName("edible_parts") val edibleParts: String? = null,
    @SerialName("permapeople_description") val permapeopleDescription: String? = null,
    @SerialName("permapeople_link") val permapeopleLink: String? = null,
    @SerialName("image_filename") val imageFilename: String? = null,
    val difficulty: String? = null,
    @SerialName("good_neighbors") val goodNeighbors: List<String> = emptyList(),
    @SerialName("bad_neighbors") val badNeighbors: List<String> = emptyList(),
    @SerialName("how_to_grow") val howToGrow: JsonElement? = null,
    val faqs: JsonElement? = null,
    val nutrition: JsonElement? = null,
    @SerialName("bloom_months") val bloomMonths: String? = null,
    @SerialName("fruit_months") val fruitMonths: String? = null,
    @SerialName("growth_months") val growthMonths: String? = null,
    val images: List<LibraryImage> = emptyList(),
)

@Serializable
data class LibraryImage(
    val id: Int,
    val filename: String,
    val source: String? = null,
    val attribution: String? = null,
    @SerialName("is_primary") val isPrimary: Boolean = false,
)
