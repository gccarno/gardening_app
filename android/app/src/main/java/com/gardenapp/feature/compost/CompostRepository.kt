package com.gardenapp.feature.compost

import com.gardenapp.core.model.CompostBin
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CompostRepository @Inject constructor(
    private val api: ApiService,
) {
    suspend fun getBins(gardenId: Int): NetworkResult<List<CompostBin>> = try {
        NetworkResult.Success(api.getCompostBins(gardenId))
    } catch (e: Exception) {
        e.toNetworkError("CompostRepository")
    }

    suspend fun createBin(
        gardenId: Int,
        name: String,
        startedDate: String?,
    ): NetworkResult<CompostBin> = try {
        val body = buildMap<String, Any?> {
            put("name", name)
            startedDate?.let { put("started_date", it) }
        }
        NetworkResult.Success(api.createCompostBin(gardenId, body))
    } catch (e: Exception) {
        e.toNetworkError("CompostRepository")
    }

    suspend fun advanceStage(binId: Int): NetworkResult<CompostBin> = try {
        NetworkResult.Success(api.advanceCompostStage(binId))
    } catch (e: Exception) {
        e.toNetworkError("CompostRepository")
    }

    suspend fun addMaterial(
        binId: Int,
        material: String,
        quantityLbs: Double?,
    ): NetworkResult<CompostBin> = try {
        val body = buildMap<String, Any?> {
            put("material", material)
            quantityLbs?.let { put("quantity_lbs", it) }
        }
        NetworkResult.Success(api.addCompostMaterial(binId, body))
    } catch (e: Exception) {
        e.toNetworkError("CompostRepository")
    }

    suspend fun deleteBin(binId: Int): NetworkResult<Unit> = try {
        api.deleteCompostBin(binId)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        e.toNetworkError("CompostRepository")
    }
}
