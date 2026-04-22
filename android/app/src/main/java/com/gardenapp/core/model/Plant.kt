package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Plant(
    val id: Int,
    val name: String,
    val type: String? = null,
    val status: String? = null,
    val notes: String? = null,
    @SerialName("planted_date") val plantedDate: String? = null,
    @SerialName("transplant_date") val transplantDate: String? = null,
    @SerialName("expected_harvest") val expectedHarvest: String? = null,
    @SerialName("garden_id") val gardenId: Int? = null,
    @SerialName("library_id") val libraryId: Int? = null,
    @SerialName("image_filename") val imageFilename: String? = null,
    @SerialName("scientific_name") val scientificName: String? = null,
    val sunlight: String? = null,
    @SerialName("days_to_harvest") val daysToHarvest: Int? = null,
    @SerialName("days_to_germination") val daysToGermination: Int? = null,
    @SerialName("sow_indoor_weeks") val sowIndoorWeeks: Int? = null,
    @SerialName("direct_sow_offset") val directSowOffset: Int? = null,
    @SerialName("transplant_offset") val transplantOffset: Int? = null,
    @SerialName("temp_max_f") val tempMaxF: Float? = null,
    @SerialName("bed_names") val bedNames: List<String> = emptyList(),
)

@Serializable
data class PlantDetail(
    val id: Int,
    val name: String,
    val type: String? = null,
    val status: String? = null,
    val notes: String? = null,
    @SerialName("planted_date") val plantedDate: String? = null,
    @SerialName("transplant_date") val transplantDate: String? = null,
    @SerialName("expected_harvest") val expectedHarvest: String? = null,
    @SerialName("garden_id") val gardenId: Int? = null,
    @SerialName("library_id") val libraryId: Int? = null,
    @SerialName("image_filename") val imageFilename: String? = null,
    @SerialName("bed_assignments") val bedAssignments: List<BedAssignment> = emptyList(),
    val tasks: List<PlantTask> = emptyList(),
    val today: String = "",
    val library: LibraryEntry? = null,
)

@Serializable
data class BedAssignment(
    @SerialName("bp_id") val bpId: Int,
    @SerialName("bed_id") val bedId: Int,
    @SerialName("bed_name") val bedName: String,
    @SerialName("garden_name") val gardenName: String? = null,
)

@Serializable
data class PlantTask(
    val id: Int,
    val title: String,
    @SerialName("task_type") val taskType: String? = null,
    @SerialName("due_date") val dueDate: String? = null,
    val completed: Boolean = false,
)
