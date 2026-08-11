package com.gardenapp

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.gardenapp.core.database.CacheCleaner
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.database.entities.BedGridCacheEntity
import com.gardenapp.core.database.entities.CacheMetaEntity
import com.gardenapp.core.database.entities.DashboardCacheEntity
import com.gardenapp.core.database.entities.GardenEntity
import com.gardenapp.core.database.entities.NotificationSettingsEntity
import com.gardenapp.core.database.entities.PlantDetailCacheEntity
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CacheDaoTest {

    private lateinit var db: GardenDatabase

    @Before
    fun createDb() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            GardenDatabase::class.java,
        ).allowMainThreadQueries().build()
    }

    @After
    fun closeDb() = db.close()

    @Test
    fun dashboardBlob_roundTrips() = runTest {
        db.cacheDao().upsertDashboard(
            DashboardCacheEntity(gardenId = 3, data = """{"season":"Summer"}""", fetchedAt = 1000L)
        )

        val result = db.cacheDao().getDashboard(3)
        assertEquals("""{"season":"Summer"}""", result?.data)
        assertEquals(1000L, result?.fetchedAt)
    }

    @Test
    fun bedGridBlob_roundTrips() = runTest {
        db.cacheDao().upsertBedGrid(
            BedGridCacheEntity(bedId = 7, data = """{"placed":[]}""", fetchedAt = 2000L)
        )

        assertEquals("""{"placed":[]}""", db.cacheDao().getBedGrid(7)?.data)
        assertNull(db.cacheDao().getBedGrid(8))
    }

    @Test
    fun plantDetailBlob_roundTrips() = runTest {
        db.cacheDao().upsertPlantDetail(
            PlantDetailCacheEntity(plantId = 12, data = """{"name":"Tomato"}""", fetchedAt = 3000L)
        )

        assertEquals("""{"name":"Tomato"}""", db.cacheDao().getPlantDetail(12)?.data)
    }

    @Test
    fun upsertOverwritesBothDataAndFetchedAt() = runTest {
        db.cacheDao().upsertDashboard(DashboardCacheEntity(1, """{"a":1}""", fetchedAt = 1000L))
        db.cacheDao().upsertDashboard(DashboardCacheEntity(1, """{"a":2}""", fetchedAt = 5000L))

        val result = db.cacheDao().getDashboard(1)
        assertEquals("""{"a":2}""", result?.data)
        assertEquals(5000L, result?.fetchedAt)
    }

    @Test
    fun isStale_comparesAgainstTtl() = runTest {
        val now = System.currentTimeMillis()
        db.cacheDao().upsertDashboard(DashboardCacheEntity(1, "{}", fetchedAt = now - 60_000L))

        val row = db.cacheDao().getDashboard(1)!!
        assertFalse("1 min old against a 5 min TTL is fresh", row.isStale(5 * 60_000L))
        assertTrue("1 min old against a 30 s TTL is stale", row.isStale(30_000L))
    }

    @Test
    fun meta_isDayKeyed() = runTest {
        db.cacheDao().upsertMeta(CacheMetaEntity("tip:2026-08-11", "Mulch your beds"))

        assertEquals("Mulch your beds", db.cacheDao().getMeta("tip:2026-08-11")?.value)
        assertNull("yesterday's key must miss", db.cacheDao().getMeta("tip:2026-08-10"))
    }

    @Test
    fun deleteMetaByPrefix_clearsOnlyThatPrefix() = runTest {
        db.cacheDao().upsertMeta(CacheMetaEntity("tip:2026-08-10", "Old tip"))
        db.cacheDao().upsertMeta(CacheMetaEntity("tip:2026-08-11", "New tip"))
        db.cacheDao().upsertMeta(CacheMetaEntity("default_garden_id", "4"))

        db.cacheDao().deleteMetaByPrefix("tip:")

        assertNull(db.cacheDao().getMeta("tip:2026-08-10"))
        assertNull(db.cacheDao().getMeta("tip:2026-08-11"))
        assertEquals("4", db.cacheDao().getMeta("default_garden_id")?.value)
    }

    @Test
    fun clearAll_wipesCachesButKeepsNotificationSettings() = runTest {
        db.gardenDao().upsertGarden(GardenEntity(id = 1, name = "Backyard"))
        db.cacheDao().upsertDashboard(DashboardCacheEntity(1, "{}"))
        db.cacheDao().upsertBedGrid(BedGridCacheEntity(7, "{}"))
        db.cacheDao().upsertPlantDetail(PlantDetailCacheEntity(12, "{}"))
        db.cacheDao().upsertMeta(CacheMetaEntity("default_garden_id", "1"))
        db.notificationSettingsDao().upsert(
            NotificationSettingsEntity(gardenId = 1, type = "WATERING", enabled = true)
        )

        CacheCleaner(db).clearAll()

        assertNull(db.gardenDao().getGarden(1))
        assertNull(db.cacheDao().getDashboard(1))
        assertNull(db.cacheDao().getBedGrid(7))
        assertNull(db.cacheDao().getPlantDetail(12))
        assertNull(db.cacheDao().getMeta("default_garden_id"))

        val settings = db.notificationSettingsDao().observeForGarden(1).first()
        assertEquals("notification settings are not a cache", 1, settings.size)
        assertTrue(settings[0].enabled)
    }
}
