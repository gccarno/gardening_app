package com.gardenapp.core.database.dao

import androidx.room.*
import com.gardenapp.core.database.entities.GardenEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface GardenDao {
    @Query("SELECT * FROM gardens ORDER BY name ASC")
    fun getAllGardens(): Flow<List<GardenEntity>>

    @Query("SELECT * FROM gardens WHERE id = :id")
    suspend fun getGarden(id: Int): GardenEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertGardens(gardens: List<GardenEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertGarden(garden: GardenEntity)

    @Query("DELETE FROM gardens WHERE id = :id")
    suspend fun deleteGarden(id: Int)

    @Query("DELETE FROM gardens")
    suspend fun deleteAll()
}
