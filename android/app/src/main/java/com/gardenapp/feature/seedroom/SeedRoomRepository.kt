package com.gardenapp.feature.seedroom

import com.gardenapp.core.model.SeedTray
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SeedRoomRepository @Inject constructor(
    private val api: ApiService,
) {
    suspend fun getTrays(gardenId: Int): NetworkResult<List<SeedTray>> = try {
        NetworkResult.Success(api.getSeedRoom(gardenId))
    } catch (e: Exception) {
        e.toNetworkError("SeedRoomRepository")
    }

    suspend fun addTray(
        gardenId: Int,
        slotNumber: Int,
        plantName: String,
        sowDate: String?,
        notes: String?,
    ): NetworkResult<SeedTray> = try {
        val body = buildMap<String, Any?> {
            put("slot_number", slotNumber)
            put("plant_name", plantName)
            sowDate?.let { put("sow_date", it) }
            notes?.let { put("notes", it) }
        }
        NetworkResult.Success(api.createSeedTray(gardenId, body))
    } catch (e: Exception) {
        e.toNetworkError("SeedRoomRepository")
    }

    suspend fun advanceStage(trayId: Int): NetworkResult<SeedTray> = try {
        NetworkResult.Success(api.advanceSeedTrayStage(trayId))
    } catch (e: Exception) {
        e.toNetworkError("SeedRoomRepository")
    }

    suspend fun removeTray(trayId: Int): NetworkResult<Unit> = try {
        api.deleteSeedTray(trayId)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        e.toNetworkError("SeedRoomRepository")
    }
}
