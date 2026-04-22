package com.gardenapp.feature.settings

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.SERVER_URL_KEY
import com.gardenapp.core.dataStore
import com.gardenapp.core.network.ServerConfig
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val serverUrl: String = ServerConfig.DEFAULT_BASE_URL,
    val savedMessage: String? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            context.dataStore.data
                .map { prefs -> prefs[SERVER_URL_KEY] ?: ServerConfig.DEFAULT_BASE_URL }
                .collect { url ->
                    _uiState.value = _uiState.value.copy(serverUrl = url)
                }
        }
    }

    fun updateUrl(url: String) {
        _uiState.value = _uiState.value.copy(serverUrl = url)
    }

    fun saveUrl() {
        val url = _uiState.value.serverUrl.trimEnd('/')
        viewModelScope.launch {
            context.dataStore.edit { prefs -> prefs[SERVER_URL_KEY] = url }
            ServerConfig.baseUrl = url
            _uiState.value = _uiState.value.copy(savedMessage = "Saved! Pointing to $url")
        }
    }

    fun clearSavedMessage() {
        _uiState.value = _uiState.value.copy(savedMessage = null)
    }
}
