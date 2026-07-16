package com.gardenapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.datastore.preferences.core.stringPreferencesKey
import com.gardenapp.core.dataStore
import com.gardenapp.core.network.AuthConfig
import com.gardenapp.core.network.ServerConfig
import com.gardenapp.core.ui.components.OfflineBanner
import com.gardenapp.core.ui.theme.GardenAppTheme
import com.gardenapp.core.util.NetworkMonitor
import com.gardenapp.feature.auth.AUTH_TOKEN_KEY
import com.gardenapp.feature.auth.LoginScreen
import com.gardenapp.navigation.GardenNavGraph
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

val SERVER_URL_KEY = stringPreferencesKey("server_url")

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var networkMonitor: NetworkMonitor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // null = DataStore not loaded yet (brief); drives both the server
            // URL and the login gate.
            val prefs by dataStore.data.collectAsState(initial = null)
            val serverUrl = prefs?.get(SERVER_URL_KEY)
            val authToken = prefs?.get(AUTH_TOKEN_KEY)

            LaunchedEffect(serverUrl) {
                serverUrl?.let { ServerConfig.baseUrl = it }
            }
            LaunchedEffect(authToken) {
                AuthConfig.token = authToken
            }

            val isOnline by networkMonitor.isOnline.collectAsState(initial = true)

            GardenAppTheme {
                when {
                    prefs == null -> Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) { CircularProgressIndicator() }

                    // Login is always daylight (dark ink on paper): the window
                    // background is Theme.Material.Light white, so dark-mode
                    // text would render white-on-white here.
                    authToken == null -> GardenAppTheme(darkTheme = false) {
                        Surface(
                            modifier = Modifier.fillMaxSize(),
                            color = MaterialTheme.colorScheme.background,
                        ) { LoginScreen() }
                    }

                    else -> Column(modifier = Modifier.fillMaxSize()) {
                        OfflineBanner(isOffline = !isOnline)
                        GardenNavGraph()
                    }
                }
            }
        }
    }
}
