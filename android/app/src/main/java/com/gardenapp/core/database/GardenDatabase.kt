package com.gardenapp.core.database

import androidx.room.Database
import androidx.room.RoomDatabase
import com.gardenapp.core.database.dao.BedDao
import com.gardenapp.core.database.dao.GardenDao
import com.gardenapp.core.database.dao.NotificationSettingsDao
import com.gardenapp.core.database.dao.PlantDao
import com.gardenapp.core.database.dao.TaskDao
import com.gardenapp.core.database.dao.WeatherDao
import com.gardenapp.core.database.entities.BedEntity
import com.gardenapp.core.database.entities.GardenEntity
import com.gardenapp.core.database.entities.NotificationSettingsEntity
import com.gardenapp.core.database.entities.PlantEntity
import com.gardenapp.core.database.entities.TaskEntity
import com.gardenapp.core.database.entities.WeatherCacheEntity

@Database(
    entities = [
        GardenEntity::class,
        WeatherCacheEntity::class,
        BedEntity::class,
        PlantEntity::class,
        TaskEntity::class,
        NotificationSettingsEntity::class,
    ],
    version = 6,
    exportSchema = false,
)
abstract class GardenDatabase : RoomDatabase() {
    abstract fun gardenDao(): GardenDao
    abstract fun weatherDao(): WeatherDao
    abstract fun bedDao(): BedDao
    abstract fun plantDao(): PlantDao
    abstract fun taskDao(): TaskDao
    abstract fun notificationSettingsDao(): NotificationSettingsDao
}
