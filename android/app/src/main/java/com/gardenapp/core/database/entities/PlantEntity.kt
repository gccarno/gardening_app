package com.gardenapp.core.database.entities

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gardenapp.core.model.Plant

@Entity(tableName = "plants")
data class PlantEntity(
    @PrimaryKey val id: Int,
    val name: String,
    val type: String? = null,
    val status: String? = null,
    val notes: String? = null,
    @ColumnInfo(name = "planted_date") val plantedDate: String? = null,
    @ColumnInfo(name = "transplant_date") val transplantDate: String? = null,
    @ColumnInfo(name = "expected_harvest") val expectedHarvest: String? = null,
    @ColumnInfo(name = "garden_id") val gardenId: Int? = null,
    @ColumnInfo(name = "library_id") val libraryId: Int? = null,
    @ColumnInfo(name = "image_filename") val imageFilename: String? = null,
    @ColumnInfo(name = "scientific_name") val scientificName: String? = null,
    val sunlight: String? = null,
    @ColumnInfo(name = "days_to_harvest") val daysToHarvest: Int? = null,
    @ColumnInfo(name = "days_to_germination") val daysToGermination: Int? = null,
    @ColumnInfo(name = "sow_indoor_weeks") val sowIndoorWeeks: Int? = null,
    @ColumnInfo(name = "direct_sow_offset") val directSowOffset: Int? = null,
    @ColumnInfo(name = "transplant_offset") val transplantOffset: Int? = null,
    @ColumnInfo(name = "temp_max_f") val tempMaxF: Float? = null,
    @ColumnInfo(name = "bed_names") val bedNames: String = "",
)

fun PlantEntity.toPlant() = Plant(
    id = id, name = name, type = type, status = status, notes = notes,
    plantedDate = plantedDate, transplantDate = transplantDate, expectedHarvest = expectedHarvest,
    gardenId = gardenId, libraryId = libraryId, imageFilename = imageFilename,
    scientificName = scientificName, sunlight = sunlight, daysToHarvest = daysToHarvest,
    daysToGermination = daysToGermination, sowIndoorWeeks = sowIndoorWeeks,
    directSowOffset = directSowOffset, transplantOffset = transplantOffset,
    tempMaxF = tempMaxF,
    bedNames = if (bedNames.isBlank()) emptyList() else bedNames.split(","),
)

fun Plant.toEntity() = PlantEntity(
    id = id, name = name, type = type, status = status, notes = notes,
    plantedDate = plantedDate, transplantDate = transplantDate, expectedHarvest = expectedHarvest,
    gardenId = gardenId, libraryId = libraryId, imageFilename = imageFilename,
    scientificName = scientificName, sunlight = sunlight, daysToHarvest = daysToHarvest,
    daysToGermination = daysToGermination, sowIndoorWeeks = sowIndoorWeeks,
    directSowOffset = directSowOffset, transplantOffset = transplantOffset,
    tempMaxF = tempMaxF, bedNames = bedNames.joinToString(","),
)
