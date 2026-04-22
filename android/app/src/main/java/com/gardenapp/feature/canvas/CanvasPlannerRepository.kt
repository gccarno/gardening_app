package com.gardenapp.feature.canvas

import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.CanvasPlant
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CanvasPlannerRepository @Inject constructor(private val api: ApiService) {

    suspend fun loadBeds(gardenId: Int): NetworkResult<List<Bed>> = try {
        NetworkResult.Success(api.getBeds(gardenId))
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun loadCanvasPlants(gardenId: Int): NetworkResult<List<CanvasPlant>> = try {
        NetworkResult.Success(api.getCanvasPlants(gardenId))
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun updateBedPosition(bedId: Int, posX: Float, posY: Float): NetworkResult<Unit> = try {
        api.updateBedPosition(bedId, mapOf("pos_x" to posX, "pos_y" to posY))
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun updateCanvasPlantPosition(plantId: Int, posX: Float, posY: Float): NetworkResult<Unit> = try {
        api.updateCanvasPlantPosition(plantId, mapOf("pos_x" to posX, "pos_y" to posY))
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }
}
