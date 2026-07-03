package com.gardenapp.feature.dashboard

import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DashboardRepository @Inject constructor(
    private val api: ApiService,
) {
    suspend fun getGardens(): NetworkResult<List<Garden>> = safeApiCall { api.getGardens() }

    suspend fun getDashboard(gardenId: Int?): NetworkResult<DashboardData> =
        safeApiCall { api.getDashboard(gardenId) }

    suspend fun getWeather(gardenId: Int): NetworkResult<WeatherData> =
        safeApiCall { api.getGardenWeather(gardenId) }

    suspend fun getDefaultGardenId(): Int? = try {
        val result = api.getDefaultGarden()
        (result as? JsonObject)?.get("garden_id")?.jsonPrimitive?.int
    } catch (e: Exception) {
        null
    }

    suspend fun logRain(gardenId: Int, rainfallIn: Float, entryDate: String): NetworkResult<Unit> =
        safeApiCall {
            api.logRain(gardenId, mapOf("rainfall_in" to rainfallIn, "entry_date" to entryDate))
            Unit
        }

    suspend fun getTipOfDay(): String? = try {
        val result = api.getTipOfDay()
        (result as? JsonObject)?.get("tip")?.jsonPrimitive?.contentOrNull
    } catch (e: Exception) {
        null
    }

    private suspend fun <T> safeApiCall(block: suspend () -> T): NetworkResult<T> = try {
        NetworkResult.Success(block())
    } catch (e: Exception) {
        e.toNetworkError("DashboardRepository")
    }
}
