package com.gardenapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.datastore.preferences.core.stringPreferencesKey
import com.gardenapp.core.dataStore
import com.gardenapp.core.network.ServerConfig
import com.gardenapp.core.ui.components.OfflineBanner
import com.gardenapp.core.ui.theme.GardenAppTheme
import com.gardenapp.core.util.NetworkMonitor
import com.gardenapp.navigation.GardenNavGraph
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.map
import javax.inject.Inject

val SERVER_URL_KEY = stringPreferencesKey("server_url")

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var networkMonitor: NetworkMonitor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val serverUrl by dataStore.data
                .map { prefs -> prefs[SERVER_URL_KEY] }
                .collectAsState(initial = null)

            LaunchedEffect(serverUrl) {
                serverUrl?.let { ServerConfig.baseUrl = it }
            }

            val isOnline by networkMonitor.isOnline.collectAsState(initial = true)

            GardenAppTheme {
                Column(modifier = Modifier.fillMaxSize()) {
                    OfflineBanner(isOffline = !isOnline)
                    GardenNavGraph()
                }
            }
        }
    }
}
