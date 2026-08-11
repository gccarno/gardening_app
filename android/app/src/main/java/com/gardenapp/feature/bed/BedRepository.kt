package com.gardenapp.feature.bed

import android.util.Log
import com.gardenapp.core.database.dao.BedDao
import com.gardenapp.core.database.dao.CacheDao
import com.gardenapp.core.database.entities.BedGridCacheEntity
import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.database.entities.toBed
import com.gardenapp.core.database.entities.toEntity
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.BedGridResponse
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.GridPlant
import com.gardenapp.core.model.HealthScore
import com.gardenapp.core.model.LibraryListEntry
import com.gardenapp.core.model.LibraryListResponse
import com.gardenapp.core.model.PlantObservation
import com.gardenapp.core.model.RotationWarnings
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
class BedRepository @Inject constructor(
    private val api: ApiService,
    private val bedDao: BedDao,
    private val cacheDao: CacheDao,
    private val json: Json,
) {
    val beds: Flow<List<Bed>> = bedDao.getAllBeds().map { list -> list.map { it.toBed() } }

    fun bedsForGarden(gardenId: Int): Flow<List<Bed>> =
        bedDao.getBedsByGarden(gardenId).map { list -> list.map { it.toBed() } }

    suspend fun refreshBeds(gardenId: Int): NetworkResult<List<Bed>> = try {
        Log.d(TAG, "refreshBeds gardenId=$gardenId")
        val fresh = api.getBeds(gardenId)
        bedDao.upsertBeds(fresh.map { it.toEntity() })
        Log.d(TAG, "refreshBeds ok count=${fresh.size}")
        NetworkResult.Success(fresh)
    } catch (e: Exception) {
        Log.e(TAG, "refreshBeds error: ${e::class.simpleName}: ${e.message}")
        e.toNetworkError("BedRepository")
    }

    suspend fun getBed(id: Int): NetworkResult<Bed> = try {
        Log.d(TAG, "getBed id=$id")
        val bed = api.getBed(id)
        bedDao.upsertBed(bed.toEntity())
        Log.d(TAG, "getBed ok name='${bed.name}'")
        NetworkResult.Success(bed)
    } catch (e: Exception) {
        Log.e(TAG, "getBed error: ${e::class.simpleName}: ${e.message}")
        val cached = bedDao.getBed(id)?.toBed()
        if (cached != null) NetworkResult.Success(cached)
        else NetworkResult.Error(e.message ?: "Not found")
    }

    suspend fun createBed(gardenId: Int, fields: Map<String, Any?>): NetworkResult<Bed> =
        try {
            Log.d(TAG, "createBed gardenId=$gardenId fields=${fields.keys}")
            val body = fields + mapOf("garden_id" to gardenId)
            val bed = api.createBed(body)
            bedDao.upsertBed(bed.toEntity())
            Log.d(TAG, "createBed ok id=${bed.id}")
            NetworkResult.Success(bed)
        } catch (e: Exception) {
            Log.e(TAG, "createBed error: ${e::class.simpleName}: ${e.message}")
            NetworkResult.Error(e.message ?: "Create failed")
        }

    suspend fun updateBed(id: Int, fields: Map<String, Any?>): NetworkResult<Unit> = try {
        Log.d(TAG, "updateBed id=$id fields=${fields.keys}")
        api.updateBed(id, fields)
        val bed = api.getBed(id)
        bedDao.upsertBed(bed.toEntity())
        Log.d(TAG, "updateBed ok")
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        Log.e(TAG, "updateBed error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Update failed")
    }

    suspend fun deleteBed(id: Int): NetworkResult<Unit> = try {
        Log.d(TAG, "deleteBed id=$id")
        api.deleteBed(id)
        bedDao.deleteBed(id)
        Log.d(TAG, "deleteBed ok")
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        Log.e(TAG, "deleteBed error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Delete failed")
    }

    // ── Grid operations ──────────────────────────────────────────────────────

    /** Local only, so the grid can be on screen before the network is touched. */
    suspend fun cachedBedGrid(bedId: Int): Cached<BedGridResponse>? =
        cacheDao.getBedGrid(bedId)?.let { row ->
            Cached(
                withContext(Dispatchers.Default) { json.decodeFromString(row.data) },
                row.fetchedAt,
            )
        }

    suspend fun refreshBedGrid(
        bedId: Int,
        force: Boolean = false,
    ): NetworkResult<Cached<BedGridResponse>> = try {
        val row = cacheDao.getBedGrid(bedId)
        if (!force && row != null && !row.isStale(GRID_TTL_MS)) {
            Log.d(TAG, "refreshBedGrid bedId=$bedId served from cache")
            NetworkResult.Success(
                Cached(
                    withContext(Dispatchers.Default) { json.decodeFromString(row.data) },
                    row.fetchedAt,
                )
            )
        } else {
            Log.d(TAG, "refreshBedGrid bedId=$bedId")
            val result = api.getBedGrid(bedId)
            Log.d(TAG, "refreshBedGrid ok bed='${result.bed.name}' placed=${result.placed.size}")
            NetworkResult.Success(Cached(result, cacheBedGrid(bedId, result)))
        }
    } catch (e: Exception) {
        Log.e(TAG, "refreshBedGrid error: ${e::class.simpleName}: ${e.message}")
        e.toNetworkError("BedRepository")
    }

    /**
     * Write-through after a placement or removal. Without it, leaving the screen and
     * coming back inside the TTL would show the plant the user just deleted.
     *
     * @return the timestamp stored, so callers can keep their staleness line honest.
     */
    suspend fun cacheBedGrid(bedId: Int, grid: BedGridResponse): Long {
        val now = System.currentTimeMillis()
        cacheDao.upsertBedGrid(
            BedGridCacheEntity(
                bedId = bedId,
                data = withContext(Dispatchers.Default) { json.encodeToString(grid) },
                fetchedAt = now,
            )
        )
        return now
    }

    suspend fun placePlant(bedId: Int, gridX: Int, gridY: Int, libraryId: Int, spacingIn: Int): NetworkResult<GridPlant> =
        try {
            Log.d(TAG, "placePlant bedId=$bedId gridX=$gridX gridY=$gridY libraryId=$libraryId")
            val body = mapOf("grid_x" to gridX, "grid_y" to gridY,
                "library_id" to libraryId, "spacing_in" to spacingIn)
            val result = api.placePlantInGrid(bedId, body)
            Log.d(TAG, "placePlant ok id=${result.id} name='${result.plantName}'")
            NetworkResult.Success(result)
        } catch (e: Exception) {
            Log.e(TAG, "placePlant error: ${e::class.simpleName}: ${e.message}")
            NetworkResult.Error(e.message ?: "Place failed")
        }

    suspend fun removePlant(bedPlantId: Int): NetworkResult<Unit> = try {
        Log.d(TAG, "removePlant bedPlantId=$bedPlantId")
        api.deleteBedPlant(bedPlantId)
        Log.d(TAG, "removePlant ok")
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        Log.e(TAG, "removePlant error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Remove failed")
    }

    suspend fun getBedPlant(id: Int): NetworkResult<BedPlantDetail> = try {
        Log.d(TAG, "getBedPlant id=$id")
        val result = api.getBedPlant(id)
        Log.d(TAG, "getBedPlant ok name='${result.plantName}'")
        NetworkResult.Success(result)
    } catch (e: Exception) {
        Log.e(TAG, "getBedPlant error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Load failed")
    }

    /**
     * Only non-null values are sent. The backend writes exactly the keys present in
     * the body, so omitting a field leaves it untouched.
     */
    suspend fun saveCare(
        bedPlantId: Int,
        lastWatered: String? = null,
        lastFertilized: String? = null,
        lastHarvest: String? = null,
        healthNotes: String? = null,
        stage: String? = null,
        plantedDate: String? = null,
        transplantDate: String? = null,
        plantNotes: String? = null,
    ): NetworkResult<Unit> =
        try {
            Log.d(TAG, "saveCare bedPlantId=$bedPlantId")
            val body = mutableMapOf<String, Any?>()
            lastWatered?.let { body["last_watered"] = it }
            lastFertilized?.let { body["last_fertilized"] = it }
            lastHarvest?.let { body["last_harvest"] = it }
            healthNotes?.let { body["health_notes"] = it }
            stage?.let { body["stage"] = it }
            plantedDate?.let { body["planted_date"] = it }
            transplantDate?.let { body["transplant_date"] = it }
            plantNotes?.let { body["plant_notes"] = it }
            api.updateBedPlantCare(bedPlantId, body)
            Log.d(TAG, "saveCare ok")
            NetworkResult.Success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "saveCare error: ${e::class.simpleName}: ${e.message}")
            NetworkResult.Error(e.message ?: "Care save failed")
        }

    // ── Library search for plant picker ──────────────────────────────────────

    suspend fun searchLibrary(query: String, page: Int = 1): NetworkResult<LibraryListResponse> = try {
        val result = api.getLibrary(query = query.takeIf { it.isNotBlank() }, page = page, perPage = 30)
        NetworkResult.Success(result)
    } catch (e: Exception) {
        Log.e(TAG, "searchLibrary error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Search failed")
    }

    // ── Rotation warnings ────────────────────────────────────────────────────

    suspend fun getRotationWarnings(bedId: Int, libraryId: Int? = null): NetworkResult<RotationWarnings> = try {
        NetworkResult.Success(api.getRotationWarnings(bedId, libraryId))
    } catch (e: Exception) {
        Log.e(TAG, "getRotationWarnings error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Load failed")
    }

    // ── Observations ─────────────────────────────────────────────────────────

    suspend fun getObservations(bedPlantId: Int): NetworkResult<List<PlantObservation>> = try {
        NetworkResult.Success(api.getObservations(bedPlantId))
    } catch (e: Exception) {
        Log.e(TAG, "getObservations error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Load failed")
    }

    suspend fun createObservation(
        bedPlantId: Int,
        observationType: String,
        severity: Int,
        notes: String?,
        observationDate: String?,
    ): NetworkResult<PlantObservation> = try {
        val body = buildMap<String, Any?> {
            put("observation_type", observationType)
            put("severity", severity)
            notes?.let { put("notes", it) }
            observationDate?.let { put("observation_date", it) }
        }
        NetworkResult.Success(api.createObservation(bedPlantId, body))
    } catch (e: Exception) {
        Log.e(TAG, "createObservation error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Create failed")
    }

    suspend fun deleteObservation(obsId: Int): NetworkResult<Unit> = try {
        api.deleteObservation(obsId)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        Log.e(TAG, "deleteObservation error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Delete failed")
    }

    suspend fun getHealthScore(bedPlantId: Int): NetworkResult<HealthScore> = try {
        NetworkResult.Success(api.getHealthScore(bedPlantId))
    } catch (e: Exception) {
        Log.e(TAG, "getHealthScore error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Load failed")
    }

    companion object {
        private const val TAG = "BedRepo"

        /** Short: the grid is edited from this very screen, and edits write through. */
        private const val GRID_TTL_MS = 2 * 60 * 1000L
    }
}
