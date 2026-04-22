package com.gardenapp

import android.app.Application
import com.gardenapp.core.network.ServerConfig
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class GardenApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Server URL is initialized from DataStore in MainActivity after it's ready.
        // ServerConfig.DEFAULT_BASE_URL is used until then.
    }
}
