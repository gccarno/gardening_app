package com.gardenapp.feature.auth

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.dataStore
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.ServerConfig
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

private val SERVER_URL_KEY = stringPreferencesKey("server_url")

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val serverUrl: String = ServerConfig.baseUrl,
    val showServerField: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val repository: AuthRepository,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun setEmail(v: String) { _uiState.value = _uiState.value.copy(email = v, error = null) }
    fun setPassword(v: String) { _uiState.value = _uiState.value.copy(password = v, error = null) }
    fun setServerUrl(v: String) { _uiState.value = _uiState.value.copy(serverUrl = v, error = null) }
    fun toggleServerField() {
        _uiState.value = _uiState.value.copy(showServerField = !_uiState.value.showServerField)
    }

    fun login() {
        val s = _uiState.value
        if (s.email.isBlank() || s.password.isBlank() || s.isLoading) return
        viewModelScope.launch {
            _uiState.value = s.copy(isLoading = true, error = null)
            val url = s.serverUrl.trim().trimEnd('/')
            if (url.isNotBlank() && url != ServerConfig.baseUrl) {
                ServerConfig.baseUrl = url
                context.dataStore.edit { prefs -> prefs[SERVER_URL_KEY] = url }
            }
            when (val result = repository.login(s.email, s.password)) {
                is NetworkResult.Success -> {
                    // Token persisted in DataStore — MainActivity flips to the app.
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
                is NetworkResult.Error -> {
                    val msg = if (result.code == 401) "Invalid email or password"
                              else "Could not reach the server. Check the server URL."
                    _uiState.value = _uiState.value.copy(isLoading = false, error = msg)
                }
                else -> Unit
            }
        }
    }
}
