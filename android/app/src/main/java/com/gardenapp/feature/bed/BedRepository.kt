package com.gardenapp.feature.bed

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
        val fresh = api.getBeds(gardenId)
        bedDao.upsertBeds(fresh.map { it.toEntity() })
        NetworkResult.Success(fresh)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun getBed(id: Int): NetworkResult<Bed> = try {
        val bed = api.getBed(id)
        bedDao.upsertBed(bed.toEntity())
        NetworkResult.Success(bed)
    } catch (e: Exception) {
        val cached = bedDao.getBed(id)?.toBed()
        if (cached != null) NetworkResult.Success(cached)
        else NetworkResult.Error(e.message ?: "Not found")
    }

    suspend fun createBed(gardenId: Int, name: String, widthFt: Float, heightFt: Float): NetworkResult<Bed> =
        try {
            val body = mapOf("name" to name, "garden_id" to gardenId,
                "width_ft" to widthFt, "height_ft" to heightFt)
            val resp = api.createBed(body)
            // Response is {ok, bed: {...}} — re-fetch to get full object
            refreshBeds(gardenId)
            val created = api.getBeds(gardenId).find { it.name == name }
            if (created != null) NetworkResult.Success(created)
            else NetworkResult.Error("Created but could not retrieve")
        } catch (e: Exception) {
            NetworkResult.Error(e.message ?: "Create failed")
        }

    suspend fun updateBed(id: Int, fields: Map<String, Any?>): NetworkResult<Unit> = try {
        api.updateBed(id, fields)
        // Re-fetch to get updated data
        val bed = api.getBed(id)
        bedDao.upsertBed(bed.toEntity())
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Update failed")
    }

    suspend fun deleteBed(id: Int): NetworkResult<Unit> = try {
        api.deleteBed(id)
        bedDao.deleteBed(id)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Delete failed")
    }

    // ── Grid operations ──────────────────────────────────────────────────────

    suspend fun getBedGrid(bedId: Int): NetworkResult<BedGridResponse> = try {
        NetworkResult.Success(api.getBedGrid(bedId))
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Grid load failed")
    }

    suspend fun placePlant(bedId: Int, gridX: Int, gridY: Int, libraryId: Int, spacingIn: Int): NetworkResult<GridPlant> =
        try {
            val body = mapOf("grid_x" to gridX, "grid_y" to gridY,
                "library_id" to libraryId, "spacing_in" to spacingIn)
            NetworkResult.Success(api.placePlantInGrid(bedId, body))
        } catch (e: Exception) {
            NetworkResult.Error(e.message ?: "Place failed")
        }

    suspend fun removePlant(bedPlantId: Int): NetworkResult<Unit> = try {
        api.deleteBedPlant(bedPlantId)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Remove failed")
    }

    suspend fun getBedPlant(id: Int): NetworkResult<BedPlantDetail> = try {
        NetworkResult.Success(api.getBedPlant(id))
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Load failed")
    }

    suspend fun saveCare(bedPlantId: Int, lastWatered: String?, lastFertilized: String?, healthNotes: String?): NetworkResult<Unit> =
        try {
            val body = mutableMapOf<String, Any?>()
            lastWatered?.let { body["last_watered"] = it }
            lastFertilized?.let { body["last_fertilized"] = it }
            healthNotes?.let { body["health_notes"] = it }
            api.updateBedPlantCare(bedPlantId, body)
            NetworkResult.Success(Unit)
        } catch (e: Exception) {
            NetworkResult.Error(e.message ?: "Care save failed")
        }

    // ── Library search for plant picker ──────────────────────────────────────

    suspend fun searchLibrary(query: String, page: Int = 1): NetworkResult<LibraryListResponse> = try {
        NetworkResult.Success(api.getLibrary(query = query.takeIf { it.isNotBlank() }, page = page, perPage = 30))
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Search failed")
    }
}
