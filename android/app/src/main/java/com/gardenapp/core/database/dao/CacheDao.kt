package com.gardenapp.core.database.dao

import androidx.room.*
import com.gardenapp.core.database.entities.BedGridCacheEntity
import com.gardenapp.core.database.entities.CacheMetaEntity
import com.gardenapp.core.database.entities.DashboardCacheEntity
import com.gardenapp.core.database.entities.PlantDetailCacheEntity

@Dao
interface CacheDao {
    // ── Dashboard ────────────────────────────────────────────────────────────

    @Query("SELECT * FROM dashboard_cache WHERE garden_id = :gardenId")
    suspend fun getDashboard(gardenId: Int): DashboardCacheEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertDashboard(cache: DashboardCacheEntity)

    @Query("DELETE FROM dashboard_cache WHERE garden_id = :gardenId")
    suspend fun deleteDashboard(gardenId: Int)

    @Query("DELETE FROM dashboard_cache")
    suspend fun clearDashboard()

    // ── Bed grid ─────────────────────────────────────────────────────────────

    @Query("SELECT * FROM bed_grid_cache WHERE bed_id = :bedId")
    suspend fun getBedGrid(bedId: Int): BedGridCacheEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertBedGrid(cache: BedGridCacheEntity)

    @Query("DELETE FROM bed_grid_cache")
    suspend fun clearBedGrid()

    // ── Plant detail ─────────────────────────────────────────────────────────

    @Query("SELECT * FROM plant_detail_cache WHERE plant_id = :plantId")
    suspend fun getPlantDetail(plantId: Int): PlantDetailCacheEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertPlantDetail(cache: PlantDetailCacheEntity)

    @Query("DELETE FROM plant_detail_cache")
    suspend fun clearPlantDetail()

    // ── Meta (scalars) ───────────────────────────────────────────────────────

    @Query("SELECT * FROM cache_meta WHERE cache_key = :key")
    suspend fun getMeta(key: String): CacheMetaEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertMeta(meta: CacheMetaEntity)

    @Query("DELETE FROM cache_meta WHERE cache_key LIKE :prefix || '%'")
    suspend fun deleteMetaByPrefix(prefix: String)

    @Query("DELETE FROM cache_meta")
    suspend fun clearMeta()
}
