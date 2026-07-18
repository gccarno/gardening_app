package com.gardenapp.core.di

import android.content.Context
import androidx.room.Room
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.database.dao.BedDao
import com.gardenapp.core.database.dao.GardenDao
import com.gardenapp.core.database.dao.NotificationSettingsDao
import com.gardenapp.core.database.dao.PlantDao
import com.gardenapp.core.database.dao.TaskDao
import com.gardenapp.core.database.dao.WeatherDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): GardenDatabase =
        Room.databaseBuilder(context, GardenDatabase::class.java, "garden_app.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideGardenDao(db: GardenDatabase): GardenDao = db.gardenDao()

    @Provides
    fun provideWeatherDao(db: GardenDatabase): WeatherDao = db.weatherDao()

    @Provides
    fun provideBedDao(db: GardenDatabase): BedDao = db.bedDao()

    @Provides
    fun providePlantDao(db: GardenDatabase): PlantDao = db.plantDao()

    @Provides
    fun provideTaskDao(db: GardenDatabase): TaskDao = db.taskDao()

    @Provides
    fun provideNotificationSettingsDao(db: GardenDatabase): NotificationSettingsDao =
        db.notificationSettingsDao()
}
