package com.gardenapp.feature.canvas

import android.util.Log
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.CanvasPlant
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CanvasPlannerRepository @Inject constructor(private val api: ApiService) {

    suspend fun loadBeds(gardenId: Int): NetworkResult<List<Bed>> = try {
        Log.d(TAG, "loadBeds gardenId=$gardenId")
        val beds = api.getBeds(gardenId)
        Log.d(TAG, "loadBeds ok count=${beds.size}")
        NetworkResult.Success(beds)
    } catch (e: Exception) {
        Log.e(TAG, "loadBeds error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun loadCanvasPlants(gardenId: Int): NetworkResult<List<CanvasPlant>> = try {
        Log.d(TAG, "loadCanvasPlants gardenId=$gardenId")
        val plants = api.getCanvasPlants(gardenId)
        Log.d(TAG, "loadCanvasPlants ok count=${plants.size}")
        NetworkResult.Success(plants)
    } catch (e: Exception) {
        Log.e(TAG, "loadCanvasPlants error: ${e::class.simpleName}: ${e.message}")
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun updateBedPosition(bedId: Int, posX: Float, posY: Float): NetworkResult<Unit> = try {
        api.updateBedPosition(bedId, mapOf("pos_x" to posX, "pos_y" to posY))
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        Log.e(TAG, "updateBedPosition bedId=$bedId error: ${e.message}")
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun updateCanvasPlantPosition(plantId: Int, posX: Float, posY: Float): NetworkResult<Unit> = try {
        api.updateCanvasPlantPosition(plantId, mapOf("pos_x" to posX, "pos_y" to posY))
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        Log.e(TAG, "updateCanvasPlantPosition plantId=$plantId error: ${e.message}")
        NetworkResult.Error(e.message ?: "Network error")
    }

    companion object {
        private const val TAG = "CanvasRepo"
    }
}
