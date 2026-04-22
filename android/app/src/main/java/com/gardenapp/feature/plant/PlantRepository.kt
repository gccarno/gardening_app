package com.gardenapp.feature.plant

import com.gardenapp.core.database.dao.PlantDao
import com.gardenapp.core.database.entities.toEntity
import com.gardenapp.core.database.entities.toPlant
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.PlantDetail
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PlantRepository @Inject constructor(
    private val api: ApiService,
    private val plantDao: PlantDao,
) {
    val plants: Flow<List<Plant>> = plantDao.getAllPlants().map { list -> list.map { it.toPlant() } }

    suspend fun refresh(): NetworkResult<List<Plant>> = try {
        val fresh = api.getPlants()
        plantDao.upsertAll(fresh.map { it.toEntity() })
        NetworkResult.Success(fresh)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun getDetail(id: Int): NetworkResult<PlantDetail> = try {
        NetworkResult.Success(api.getPlant(id))
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun setStatus(id: Int, status: String): NetworkResult<Plant> = try {
        val result = api.setPlantStatus(id, mapOf("status" to status))
        plantDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun createPlant(
        name: String,
        gardenId: Int?,
        libraryId: Int?,
        plantedDate: String?,
        notes: String?,
    ): NetworkResult<Plant> = try {
        val body = buildMap<String, Any?> {
            put("name", name)
            gardenId?.let { put("garden_id", it) }
            libraryId?.let { put("library_id", it) }
            plantedDate?.let { put("planted_date", it) }
            notes?.let { put("notes", it) }
        }
        val result = api.createPlant(body)
        plantDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun updatePlant(
        id: Int,
        name: String,
        notes: String?,
        plantedDate: String?,
        expectedHarvest: String?,
    ): NetworkResult<Plant> = try {
        val body = buildMap<String, Any?> {
            put("name", name)
            put("notes", notes)
            put("planted_date", plantedDate)
            put("expected_harvest", expectedHarvest)
        }
        val result = api.updatePlant(id, body)
        plantDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun deletePlant(id: Int): NetworkResult<Unit> = try {
        api.deletePlant(id)
        refresh()
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }
}
