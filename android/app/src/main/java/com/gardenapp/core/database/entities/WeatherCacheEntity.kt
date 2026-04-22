package com.gardenapp.core.database.entities

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "weather_cache")
data class WeatherCacheEntity(
    @PrimaryKey @ColumnInfo(name = "garden_id") val gardenId: Int,
    val data: String,    // JSON string of WeatherData
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long = System.currentTimeMillis(),
) {
    fun isStale(ttlMillis: Long = 30 * 60 * 1000L): Boolean =
        System.currentTimeMillis() - fetchedAt > ttlMillis
}
