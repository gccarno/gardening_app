package com.gardenapp.feature.auth

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.gardenapp.core.database.CacheCleaner
import com.gardenapp.core.dataStore
import com.gardenapp.core.model.AuthUser
import com.gardenapp.core.model.LoginRequest
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.AuthConfig
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

val AUTH_TOKEN_KEY = stringPreferencesKey("auth_token")

@Singleton
class AuthRepository @Inject constructor(
    private val api: ApiService,
    @ApplicationContext private val context: Context,
    private val cacheCleaner: CacheCleaner,
) {
    suspend fun login(email: String, password: String): NetworkResult<AuthUser> = try {
        val response = api.login(LoginRequest(email.trim().lowercase(), password))
        AuthConfig.token = response.token
        context.dataStore.edit { prefs -> prefs[AUTH_TOKEN_KEY] = response.token }
        NetworkResult.Success(response.user)
    } catch (e: Exception) {
        e.toNetworkError("AuthRepository")
    }

    suspend fun logout() {
        try {
            api.logout()
        } catch (_: Exception) {
            // Token may already be invalid — clear locally regardless.
        }
        AuthConfig.token = null
        context.dataStore.edit { prefs -> prefs.remove(AUTH_TOKEN_KEY) }
        // Nothing cached belongs to the next person to sign in.
        cacheCleaner.clearAll()
    }
}
