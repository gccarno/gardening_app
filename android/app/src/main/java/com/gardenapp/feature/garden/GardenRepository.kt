package com.gardenapp.feature.garden

import com.gardenapp.core.database.dao.GardenDao
import com.gardenapp.core.database.dao.WeatherDao
import com.gardenapp.core.database.entities.WeatherCacheEntity
import com.gardenapp.core.database.entities.toEntity
import com.gardenapp.core.database.entities.toGarden
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GardenRepository @Inject constructor(
    private val api: ApiService,
    private val gardenDao: GardenDao,
    private val weatherDao: WeatherDao,
    private val json: Json,
) {
    // Cached flow — emits instantly from Room, then refreshes from network
    val gardens: Flow<List<Garden>> = gardenDao.getAllGardens().map { list ->
        list.map { it.toGarden() }
    }

    suspend fun refreshGardens(): NetworkResult<List<Garden>> = try {
        val fresh = api.getGardens()
        gardenDao.upsertGardens(fresh.map { it.toEntity() })
        NetworkResult.Success(fresh)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun getGarden(id: Int): NetworkResult<Garden> = try {
        val garden = api.getGarden(id)
        gardenDao.upsertGarden(garden.toEntity())
        NetworkResult.Success(garden)
    } catch (e: Exception) {
        // fall back to cache
        val cached = gardenDao.getGarden(id)?.toGarden()
        if (cached != null) NetworkResult.Success(cached)
        else NetworkResult.Error(e.message ?: "Not found")
    }

    suspend fun createGarden(name: String, description: String?, zipCode: String?): NetworkResult<Garden> =
        try {
            val body = buildMap<String, Any?> {
                put("name", name)
                description?.let { put("description", it) }
                zipCode?.let { put("zip_code", it) }
            }
            val garden = api.createGarden(body)
            gardenDao.upsertGarden(garden.toEntity())
            NetworkResult.Success(garden)
        } catch (e: Exception) {
            NetworkResult.Error(e.message ?: "Create failed")
        }

    suspend fun updateGarden(id: Int, fields: Map<String, Any?>): NetworkResult<Garden> = try {
        val garden = api.updateGarden(id, fields)
        gardenDao.upsertGarden(garden.toEntity())
        NetworkResult.Success(garden)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Update failed")
    }

    suspend fun deleteGarden(id: Int): NetworkResult<Unit> = try {
        api.deleteGarden(id)
        gardenDao.deleteGarden(id)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Delete failed")
    }

    suspend fun getWeather(gardenId: Int): NetworkResult<WeatherData> = try {
        // Check cache first (TTL 30 min)
        val cached = weatherDao.getWeatherCache(gardenId)
        if (cached != null && !cached.isStale()) {
            return NetworkResult.Success(json.decodeFromString(cached.data))
        }
        val weather = api.getGardenWeather(gardenId)
        weatherDao.upsertWeatherCache(
            WeatherCacheEntity(gardenId = gardenId, data = json.encodeToString(weather))
        )
        NetworkResult.Success(weather)
    } catch (e: Exception) {
        // Try stale cache on error
        val stale = weatherDao.getWeatherCache(gardenId)
        if (stale != null) NetworkResult.Success(json.decodeFromString(stale.data))
        else NetworkResult.Error(e.message ?: "Weather unavailable")
    }

    suspend fun bulkCare(gardenId: Int, action: String): NetworkResult<Unit> = try {
        api.bulkCare(gardenId, mapOf("action" to action))
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Bulk care failed")
    }
}
