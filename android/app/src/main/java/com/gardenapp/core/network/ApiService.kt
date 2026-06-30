package com.gardenapp.core.network

import com.gardenapp.core.model.*
import kotlinx.serialization.json.JsonElement
import retrofit2.http.*

interface ApiService {

    // ── Health ──────────────────────────────────────────────────────────────
    @GET("health")
    suspend fun health(): JsonElement

    // ── Gardens ─────────────────────────────────────────────────────────────
    @GET("gardens")
    suspend fun getGardens(): List<Garden>

    @GET("gardens/{id}")
    suspend fun getGarden(@Path("id") id: Int): Garden

    @POST("gardens")
    suspend fun createGarden(@Body body: Map<String, @JvmSuppressWildcards Any?>): Garden

    @PUT("gardens/{id}")
    suspend fun updateGarden(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): Garden

    @DELETE("gardens/{id}")
    suspend fun deleteGarden(@Path("id") id: Int): JsonElement

    @GET("gardens/{id}/weather")
    suspend fun getGardenWeather(@Path("id") id: Int): WeatherData

    @POST("gardens/{id}/fetch-weather")
    suspend fun fetchWeatherHistory(@Path("id") id: Int): JsonElement

    @POST("gardens/{id}/bulk-care")
    suspend fun bulkCare(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @GET("gardens/{id}/watering-status")
    suspend fun getWateringStatus(@Path("id") id: Int): JsonElement

    @GET("gardens/{id}/annotations")
    suspend fun getAnnotations(@Path("id") id: Int): JsonElement

    @POST("gardens/{id}/annotations")
    suspend fun saveAnnotations(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @GET("gardens/{id}/canvas-plants")
    suspend fun getCanvasPlants(@Path("id") id: Int): List<CanvasPlant>

    @POST("gardens/{id}/canvas-plants")
    suspend fun createCanvasPlant(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): CanvasPlant

    @GET("gardens/{id}/tasks")
    suspend fun getGardenTasks(@Path("id") id: Int): List<Task>

    @POST("gardens/{id}/quick-task")
    suspend fun createQuickTask(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @GET("dashboard")
    suspend fun getDashboard(@Query("garden_id") gardenId: Int? = null): DashboardData

    @GET("settings/default-garden")
    suspend fun getDefaultGarden(): JsonElement

    @POST("settings/default-garden")
    suspend fun setDefaultGarden(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    // ── Beds ─────────────────────────────────────────────────────────────────
    @GET("beds")
    suspend fun getBeds(@Query("garden_id") gardenId: Int? = null): List<Bed>

    @GET("beds/{id}")
    suspend fun getBed(@Path("id") id: Int): Bed

    @POST("beds")
    suspend fun createBed(@Body body: Map<String, @JvmSuppressWildcards Any?>): Bed

    @PUT("beds/{id}")
    suspend fun updateBed(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("beds/{id}/delete")
    suspend fun deleteBed(@Path("id") id: Int): JsonElement

    @POST("beds/{id}/position")
    suspend fun updateBedPosition(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("beds/{id}/assign-garden")
    suspend fun assignBedToGarden(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @GET("beds/{id}/grid")
    suspend fun getBedGrid(@Path("id") id: Int): BedGridResponse

    @POST("beds/{id}/grid-plant")
    suspend fun placePlantInGrid(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): GridPlant

    @POST("beds/{id}/grid-plant-bulk")
    suspend fun placePlantsBulk(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    // ── Bed Plants ───────────────────────────────────────────────────────────
    @POST("bedplants")
    suspend fun createBedPlant(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    @GET("bedplants/{id}")
    suspend fun getBedPlant(@Path("id") id: Int): BedPlantDetail

    @POST("bedplants/{id}/care")
    suspend fun updateBedPlantCare(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("bedplants/{id}/delete")
    suspend fun deleteBedPlant(@Path("id") id: Int): JsonElement

    @POST("bedplants/bulk-care")
    suspend fun bulkBedPlantCare(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    // ── Plants ───────────────────────────────────────────────────────────────
    @GET("plants")
    suspend fun getPlants(
        @Query("garden_id") gardenId: Int? = null,
        @Query("status") status: String? = null,
    ): List<Plant>

    @GET("plants/{id}")
    suspend fun getPlant(@Path("id") id: Int): PlantDetail

    @POST("plants")
    suspend fun createPlant(@Body body: Map<String, @JvmSuppressWildcards Any?>): Plant

    @PUT("plants/{id}")
    suspend fun updatePlant(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): Plant

    @DELETE("plants/{id}")
    suspend fun deletePlant(@Path("id") id: Int): JsonElement

    @POST("plants/{id}/status")
    suspend fun setPlantStatus(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): Plant

    @POST("plants/{id}/care")
    suspend fun recordPlantCare(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("plants/bulk-status")
    suspend fun bulkPlantStatus(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    @POST("plants/bulk-care")
    suspend fun bulkPlantCare(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    // ── Tasks ────────────────────────────────────────────────────────────────
    @GET("tasks")
    suspend fun getTasks(
        @Query("garden_id") gardenId: Int? = null,
        @Query("completed") completed: Boolean? = null,
    ): List<Task>

    @GET("tasks/{id}")
    suspend fun getTask(@Path("id") id: Int): Task

    @POST("tasks")
    suspend fun createTask(@Body body: Map<String, @JvmSuppressWildcards Any?>): Task

    @PUT("tasks/{id}")
    suspend fun updateTask(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): Task

    @POST("tasks/{id}/complete")
    suspend fun toggleTaskComplete(@Path("id") id: Int): Task

    @DELETE("tasks/{id}")
    suspend fun deleteTask(@Path("id") id: Int): JsonElement

    // ── Library ──────────────────────────────────────────────────────────────
    @GET("library")
    suspend fun getLibrary(
        @Query("q") query: String? = null,
        @Query("type") type: String? = null,
        @Query("page") page: Int? = null,
        @Query("per_page") perPage: Int? = null,
    ): LibraryListResponse

    @GET("library/{id}")
    suspend fun getLibraryEntry(@Path("id") id: Int): LibraryEntry

    @GET("library/{id}/images")
    suspend fun getLibraryImages(@Path("id") id: Int): List<LibraryImage>

    @POST("library/images/{imageId}/set-primary")
    suspend fun setImagePrimary(@Path("imageId") imageId: Int): JsonElement

    @POST("library/images/{imageId}/delete")
    suspend fun deleteLibraryImage(@Path("imageId") imageId: Int): JsonElement

    @POST("library/{id}/quick-edit")
    suspend fun quickEditLibrary(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("library/{id}/clone")
    suspend fun cloneLibraryEntry(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("library/{id}/patch")
    suspend fun patchLibraryEntry(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    // ── Perenual / Permapeople ───────────────────────────────────────────────
    @GET("perenual/search")
    suspend fun perenualSearch(@Query("q") query: String): JsonElement

    @POST("perenual/save")
    suspend fun perenualSave(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    @POST("permapeople/search")
    suspend fun permapeopleSearch(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    // ── Canvas Plants ────────────────────────────────────────────────────────
    @GET("canvas-plants/{id}")
    suspend fun getCanvasPlant(@Path("id") id: Int): CanvasPlant

    @POST("canvas-plants/{id}/position")
    suspend fun updateCanvasPlantPosition(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("canvas-plants/{id}/radius")
    suspend fun updateCanvasPlantRadius(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("canvas-plants/{id}/appearance")
    suspend fun updateCanvasPlantAppearance(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    @POST("canvas-plants/{id}/delete")
    suspend fun deleteCanvasPlant(@Path("id") id: Int): JsonElement

    @POST("canvas-plants/{id}/care")
    suspend fun recordCanvasPlantCare(
        @Path("id") id: Int,
        @Body body: Map<String, @JvmSuppressWildcards Any?>,
    ): JsonElement

    // ── Chat ─────────────────────────────────────────────────────────────────
    @POST("chat")
    suspend fun sendChat(@Body body: Map<String, @JvmSuppressWildcards Any?>): JsonElement

    @POST("chat/restart-model")
    suspend fun restartModel(): JsonElement
}
