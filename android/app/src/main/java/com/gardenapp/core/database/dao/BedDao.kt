package com.gardenapp.core.database.dao

import androidx.room.*
import com.gardenapp.core.database.entities.BedEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface BedDao {
    @Query("SELECT * FROM beds WHERE garden_id = :gardenId ORDER BY name ASC")
    fun getBedsByGarden(gardenId: Int): Flow<List<BedEntity>>

    @Query("SELECT * FROM beds ORDER BY name ASC")
    fun getAllBeds(): Flow<List<BedEntity>>

    @Query("SELECT * FROM beds WHERE id = :id")
    suspend fun getBed(id: Int): BedEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertBeds(beds: List<BedEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertBed(bed: BedEntity)

    @Query("DELETE FROM beds WHERE id = :id")
    suspend fun deleteBed(id: Int)

    @Query("DELETE FROM beds WHERE garden_id = :gardenId")
    suspend fun deleteBedsByGarden(gardenId: Int)

    @Query("DELETE FROM beds")
    suspend fun deleteAll()
}
