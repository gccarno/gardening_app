package com.gardenapp.feature.bed

import android.util.Log
import com.gardenapp.core.database.dao.BedDao
import com.gardenapp.core.database.entities.toBed
import com.gardenapp.core.database.entities.toEntity
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.BedGridResponse
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.GridPlant
import com.gardenapp.core.model.LibraryListEntry
import com.gardenapp.core.model.LibraryListResponse
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class BedRepository @Inject constructor(
    private val api: ApiService,
    private val bedDao: BedDao,
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
        NetworkResult.Error(e.message ?: "Network error")
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

    suspend fun createBed(gardenId: Int, name: String, widthFt: Float, heightFt: Float): NetworkResult<Bed> =
        try {
            Log.d(TAG, "createBed gardenId=$gardenId name='$name'")
            val body = mapOf("name" to name, "garden_id" to gardenId,
                "width_ft" to widthFt, "height_ft" to heightFt)
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

    suspend fun getBedGrid(bedId: Int): NetworkResult<BedGridResponse> = try {
        Log.d(TAG, "getBedGrid bedId=$bedId")
        val result = api.getBedGrid(bedId)
        Log.d(TAG, "getBedGrid ok bed='${result.bed.name}' placed=${result.placed.size}")
        NetworkResult.Success(result)
    } catch (e: Exception) {
        Log.e(TAG, "getBedGrid error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Grid load failed")
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

    suspend fun saveCare(bedPlantId: Int, lastWatered: String?, lastFertilized: String?, healthNotes: String?): NetworkResult<Unit> =
        try {
            Log.d(TAG, "saveCare bedPlantId=$bedPlantId")
            val body = mutableMapOf<String, Any?>()
            lastWatered?.let { body["last_watered"] = it }
            lastFertilized?.let { body["last_fertilized"] = it }
            healthNotes?.let { body["health_notes"] = it }
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

    companion object {
        private const val TAG = "BedRepo"
    }
}
