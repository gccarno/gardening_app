package com.gardenapp.feature.plant

import com.gardenapp.core.database.dao.CacheDao
import com.gardenapp.core.database.dao.PlantDao
import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.database.entities.PlantDetailCacheEntity
import com.gardenapp.core.database.entities.toEntity
import com.gardenapp.core.database.entities.toPlant
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.PlantDetail
import com.gardenapp.core.model.SyncChange
import com.gardenapp.core.model.SyncPreview
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PlantRepository @Inject constructor(
    private val api: ApiService,
    private val plantDao: PlantDao,
    private val cacheDao: CacheDao,
    private val json: Json,
) {
    val plants: Flow<List<Plant>> = plantDao.getAllPlants().map { list -> list.map { it.toPlant() } }

    suspend fun refresh(): NetworkResult<List<Plant>> = try {
        val fresh = api.getPlants()
        plantDao.upsertAll(fresh.map { it.toEntity() })
        NetworkResult.Success(fresh)
    } catch (e: Exception) {
        e.toNetworkError("PlantRepository")
    }

    /**
     * Cached in its own table rather than in `plants`: PlantDetail and Plant carry
     * different fields, and every upsert is REPLACE, so folding a detail into the
     * list table would null out the columns the list screen reads.
     */
    suspend fun cachedDetail(id: Int): Cached<PlantDetail>? =
        cacheDao.getPlantDetail(id)?.let { row ->
            Cached(
                withContext(Dispatchers.Default) { json.decodeFromString(row.data) },
                row.fetchedAt,
            )
        }

    suspend fun refreshDetail(
        id: Int,
        force: Boolean = false,
    ): NetworkResult<Cached<PlantDetail>> = try {
        val row = cacheDao.getPlantDetail(id)
        if (!force && row != null && !row.isStale(DETAIL_TTL_MS)) {
            NetworkResult.Success(
                Cached(
                    withContext(Dispatchers.Default) { json.decodeFromString(row.data) },
                    row.fetchedAt,
                )
            )
        } else {
            val fresh = api.getPlant(id)
            val now = System.currentTimeMillis()
            cacheDao.upsertPlantDetail(
                PlantDetailCacheEntity(
                    plantId = id,
                    data = withContext(Dispatchers.Default) { json.encodeToString(fresh) },
                    fetchedAt = now,
                )
            )
            NetworkResult.Success(Cached(fresh, now))
        }
    } catch (e: Exception) {
        e.toNetworkError("PlantRepository")
    }

    suspend fun setStatus(id: Int, status: String): NetworkResult<Plant> = try {
        val result = api.setPlantStatus(id, mapOf("status" to status))
        plantDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        e.toNetworkError("PlantRepository")
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
        e.toNetworkError("PlantRepository")
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
        e.toNetworkError("PlantRepository")
    }

    suspend fun deletePlant(id: Int): NetworkResult<Unit> = try {
        api.deletePlant(id)
        refresh()
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        e.toNetworkError("PlantRepository")
    }

    suspend fun getSyncPreview(): NetworkResult<SyncPreview> = try {
        NetworkResult.Success(api.getSyncPreview())
    } catch (e: Exception) {
        e.toNetworkError("PlantRepository")
    }

    suspend fun applySync(changes: List<SyncChange>): NetworkResult<Unit> = try {
        val body = mapOf("changes" to changes.map { c ->
            mapOf(
                "plant_id" to c.plantId,
                "field" to c.field,
                "proposed_value" to c.proposedValue,
            )
        })
        api.applySync(body)
        refresh()
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        e.toNetworkError("PlantRepository")
    }

    companion object {
        private const val DETAIL_TTL_MS = 5 * 60 * 1000L
    }
}
