package com.gardenapp.core.database.dao

import androidx.room.*
import com.gardenapp.core.database.entities.PlantEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PlantDao {
    @Query("SELECT * FROM plants ORDER BY name ASC")
    fun getAllPlants(): Flow<List<PlantEntity>>

    @Query("SELECT * FROM plants WHERE id = :id")
    suspend fun getById(id: Int): PlantEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(plants: List<PlantEntity>)

    @Query("DELETE FROM plants")
    suspend fun deleteAll()
}
