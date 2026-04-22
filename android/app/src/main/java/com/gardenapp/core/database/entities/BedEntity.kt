package com.gardenapp.core.database.entities

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gardenapp.core.model.Bed

@Entity(tableName = "beds")
data class BedEntity(
    @PrimaryKey val id: Int,
    val name: String,
    @ColumnInfo(name = "garden_id") val gardenId: Int? = null,
    @ColumnInfo(name = "garden_name") val gardenName: String? = null,
    @ColumnInfo(name = "width_ft") val widthFt: Float = 4f,
    @ColumnInfo(name = "height_ft") val heightFt: Float = 8f,
    @ColumnInfo(name = "depth_ft") val depthFt: Float? = null,
    val location: String? = null,
    val description: String? = null,
    @ColumnInfo(name = "soil_notes") val soilNotes: String? = null,
    @ColumnInfo(name = "soil_ph") val soilPh: Float? = null,
    @ColumnInfo(name = "clay_pct") val clayPct: Float? = null,
    @ColumnInfo(name = "compost_pct") val compostPct: Float? = null,
    @ColumnInfo(name = "sand_pct") val sandPct: Float? = null,
    @ColumnInfo(name = "plant_count") val plantCount: Int? = null,
)

fun BedEntity.toBed() = Bed(
    id = id, name = name, gardenId = gardenId, gardenName = gardenName,
    widthFt = widthFt, heightFt = heightFt, depthFt = depthFt,
    location = location, description = description, soilNotes = soilNotes,
    soilPh = soilPh, clayPct = clayPct, compostPct = compostPct, sandPct = sandPct,
    plantCount = plantCount,
)

fun Bed.toEntity() = BedEntity(
    id = id, name = name, gardenId = gardenId, gardenName = gardenName,
    widthFt = widthFt, heightFt = heightFt, depthFt = depthFt,
    location = location, description = description, soilNotes = soilNotes,
    soilPh = soilPh, clayPct = clayPct, compostPct = compostPct, sandPct = sandPct,
    plantCount = plantCount,
)
