package com.gardenapp.core.database.entities

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gardenapp.core.model.Garden

@Entity(tableName = "gardens")
data class GardenEntity(
    @PrimaryKey val id: Int,
    val name: String,
    val description: String? = null,
    val unit: String = "ft",
    @ColumnInfo(name = "zip_code") val zipCode: String? = null,
    val city: String? = null,
    val state: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @ColumnInfo(name = "usda_zone") val usdaZone: String? = null,
    @ColumnInfo(name = "zone_temp_range") val zoneTempRange: String? = null,
    @ColumnInfo(name = "last_frost_date") val lastFrostDate: String? = null,
    @ColumnInfo(name = "first_frost_date") val firstFrostDate: String? = null,
    @ColumnInfo(name = "watering_frequency_days") val wateringFrequencyDays: Int? = null,
    @ColumnInfo(name = "water_source") val waterSource: String? = null,
)

fun GardenEntity.toGarden() = Garden(
    id = id,
    name = name,
    description = description,
    unit = unit,
    zipCode = zipCode,
    city = city,
    state = state,
    latitude = latitude,
    longitude = longitude,
    usdaZone = usdaZone,
    zoneTempRange = zoneTempRange,
    lastFrostDate = lastFrostDate,
    firstFrostDate = firstFrostDate,
    wateringFrequencyDays = wateringFrequencyDays,
    waterSource = waterSource,
)

fun Garden.toEntity() = GardenEntity(
    id = id,
    name = name,
    description = description,
    unit = unit,
    zipCode = zipCode,
    city = city,
    state = state,
    latitude = latitude,
    longitude = longitude,
    usdaZone = usdaZone,
    zoneTempRange = zoneTempRange,
    lastFrostDate = lastFrostDate,
    firstFrostDate = firstFrostDate,
    wateringFrequencyDays = wateringFrequencyDays,
    waterSource = waterSource,
)
