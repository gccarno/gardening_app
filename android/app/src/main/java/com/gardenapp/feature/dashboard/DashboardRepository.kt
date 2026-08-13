package com.gardenapp.feature.dashboard

import com.gardenapp.core.database.dao.CacheDao
import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.database.entities.CacheMetaEntity
import com.gardenapp.core.database.entities.DashboardCacheEntity
import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import com.gardenapp.feature.garden.GardenRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive
import java.time.LocalDate
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Every read comes in a pair: `cachedX` touches only the database so the screen can
 * paint before the first packet leaves, and `refreshX` goes to the network unless the
 * stored row is still inside its TTL. Keeping the TTL here means the ViewModel never
 * has to reason about staleness, and "Updated 3m ago" stays truthful even when a
 * refresh was skipped.
 *
 * Gardens and weather are delegated to [GardenRepository] rather than re-fetched:
 * it already backs gardens with Room and caches weather for 30 minutes.
 */
@Singleton
class DashboardRepository @Inject constructor(
    private val api: ApiService,
    private val gardenRepository: GardenRepository,
    private val cacheDao: CacheDao,
    private val json: Json,
) {
    val gardens: Flow<List<Garden>> = gardenRepository.gardens

    suspend fun refreshGardens(): NetworkResult<List<Garden>> = gardenRepository.refreshGardens()

    suspend fun getWeather(gardenId: Int): NetworkResult<WeatherData> =
        gardenRepository.getWeather(gardenId)

    // ── Dashboard ────────────────────────────────────────────────────────────

    suspend fun cachedDashboard(gardenId: Int): Cached<DashboardData>? =
        cacheDao.getDashboard(gardenId)?.let { row ->
            Cached(decode(row.data), row.fetchedAt)
        }

    suspend fun refreshDashboard(
        gardenId: Int,
        force: Boolean = false,
    ): NetworkResult<Cached<DashboardData>> = try {
        val row = cacheDao.getDashboard(gardenId)
        if (!force && row != null && !row.isStale(DASHBOARD_TTL_MS)) {
            NetworkResult.Success(Cached(decode(row.data), row.fetchedAt))
        } else {
            val fresh = api.getDashboard(gardenId)
            val now = System.currentTimeMillis()
            cacheDao.upsertDashboard(
                DashboardCacheEntity(gardenId = gardenId, data = encode(fresh), fetchedAt = now)
            )
            NetworkResult.Success(Cached(fresh, now))
        }
    } catch (e: Exception) {
        e.toNetworkError("DashboardRepository")
    }

    // ── Default garden ───────────────────────────────────────────────────────

    /**
     * Returned regardless of age — the cold-start path depends on having an id, and a
     * stale one is a good guess. The TTL only gates whether [refreshDefaultGardenId]
     * bothers the network.
     */
    suspend fun cachedDefaultGardenId(): Int? =
        cacheDao.getMeta(KEY_DEFAULT_GARDEN)?.value?.toIntOrNull()

    suspend fun refreshDefaultGardenId(): Int? {
        val row = cacheDao.getMeta(KEY_DEFAULT_GARDEN)
        if (row != null && !row.isStale(DEFAULT_GARDEN_TTL_MS)) return row.value.toIntOrNull()
        return try {
            val id = (api.getDefaultGarden() as? JsonObject)?.get("garden_id")?.jsonPrimitive?.int
            id?.also { setDefaultGardenIdLocally(it) }
        } catch (e: Exception) {
            row?.value?.toIntOrNull()
        }
    }

    /** Also doubles as "the garden to reopen on", so switching garden sticks. */
    suspend fun setDefaultGardenIdLocally(gardenId: Int) {
        cacheDao.upsertMeta(CacheMetaEntity(KEY_DEFAULT_GARDEN, gardenId.toString()))
    }

    // ── Tip of the day ───────────────────────────────────────────────────────

    /**
     * Keyed by the day rather than a TTL: the backend derives the tip from the date,
     * so once today's tip is stored there is nothing to refresh.
     */
    suspend fun cachedTipForToday(): String? = cacheDao.getMeta(tipKey())?.value

    suspend fun refreshTipOfDay(): String? {
        cachedTipForToday()?.let { return it }
        val tip = try {
            (api.getTipOfDay() as? JsonObject)?.get("tip")?.jsonPrimitive?.contentOrNull
        } catch (e: Exception) {
            null
        } ?: return null
        cacheDao.deleteMetaByPrefix(TIP_PREFIX)   // drop yesterday's row; self-cleaning
        cacheDao.upsertMeta(CacheMetaEntity(tipKey(), tip))
        return tip
    }

    private fun tipKey() = "$TIP_PREFIX${LocalDate.now()}"

    private suspend fun decode(data: String): DashboardData =
        withContext(Dispatchers.Default) { json.decodeFromString(data) }

    private suspend fun encode(data: DashboardData): String =
        withContext(Dispatchers.Default) { json.encodeToString(data) }

    companion object {
        private const val KEY_DEFAULT_GARDEN = "default_garden_id"
        private const val TIP_PREFIX = "tip:"
        private const val DASHBOARD_TTL_MS = 5 * 60 * 1000L
        private const val DEFAULT_GARDEN_TTL_MS = 24 * 60 * 60 * 1000L
    }
}
