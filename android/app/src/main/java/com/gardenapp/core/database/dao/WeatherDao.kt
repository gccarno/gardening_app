package com.gardenapp.core.database.dao

import androidx.room.*
import com.gardenapp.core.database.entities.WeatherCacheEntity

@Dao
interface WeatherDao {
    @Query("SELECT * FROM weather_cache WHERE garden_id = :gardenId")
    suspend fun getWeatherCache(gardenId: Int): WeatherCacheEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertWeatherCache(cache: WeatherCacheEntity)

    @Query("DELETE FROM weather_cache WHERE garden_id = :gardenId")
    suspend fun deleteWeatherCache(gardenId: Int)
}
