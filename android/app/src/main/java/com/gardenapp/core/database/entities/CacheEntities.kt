package com.gardenapp.core.database.entities

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Cached payloads for screens whose responses are read whole and never queried
 * by field. Each stores the JSON of a `@Serializable` model plus the time it was
 * fetched, following [WeatherCacheEntity].
 *
 * These live together because — unlike the other entity files — they carry no
 * `toEntity()`/`toDomain()` mappers; splitting them would be four files of
 * boilerplate.
 */

/** A cached value paired with the moment it came off the wire. */
data class Cached<T>(val value: T, val fetchedAt: Long)

@Entity(tableName = "dashboard_cache")
data class DashboardCacheEntity(
    @PrimaryKey @ColumnInfo(name = "garden_id") val gardenId: Int,
    val data: String,    // JSON string of DashboardData
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long = System.currentTimeMillis(),
) {
    fun isStale(ttlMillis: Long): Boolean = System.currentTimeMillis() - fetchedAt > ttlMillis
}

@Entity(tableName = "bed_grid_cache")
data class BedGridCacheEntity(
    @PrimaryKey @ColumnInfo(name = "bed_id") val bedId: Int,
    val data: String,    // JSON string of BedGridResponse
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long = System.currentTimeMillis(),
) {
    fun isStale(ttlMillis: Long): Boolean = System.currentTimeMillis() - fetchedAt > ttlMillis
}

/**
 * Kept separate from the `plants` table on purpose: PlantDetail and Plant carry
 * different fields, and every upsert is REPLACE, so writing a detail-derived row
 * into `plants` would null out the list-screen columns (sunlight, bedNames, ...).
 */
@Entity(tableName = "plant_detail_cache")
data class PlantDetailCacheEntity(
    @PrimaryKey @ColumnInfo(name = "plant_id") val plantId: Int,
    val data: String,    // JSON string of PlantDetail
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long = System.currentTimeMillis(),
) {
    fun isStale(ttlMillis: Long): Boolean = System.currentTimeMillis() - fetchedAt > ttlMillis
}

/** Key/value for the small scalars: default garden id, tip of the day. */
@Entity(tableName = "cache_meta")
data class CacheMetaEntity(
    @PrimaryKey @ColumnInfo(name = "cache_key") val key: String,
    val value: String,
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long = System.currentTimeMillis(),
) {
    fun isStale(ttlMillis: Long): Boolean = System.currentTimeMillis() - fetchedAt > ttlMillis
}
