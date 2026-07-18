package com.gardenapp

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.database.entities.NotificationSettingsEntity
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotificationSettingsDaoTest {

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

    private val dao get() = db.notificationSettingsDao()

    @Test
    fun upsertAndObserve_roundTrip() = runTest {
        dao.upsert(NotificationSettingsEntity(
            gardenId = 1, type = "WATERING", enabled = true, frequencyDays = 3, hourOfDay = 10))
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "GROWTH"))

        val rows = dao.observeForGarden(1).first()
        assertEquals(2, rows.size)
        val watering = rows.first { it.type == "WATERING" }
        assertTrue(watering.enabled)
        assertEquals(3, watering.frequencyDays)
        assertEquals(10, watering.hourOfDay)
    }

    @Test
    fun upsert_replacesExistingRow() = runTest {
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "WATERING", enabled = true))
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "WATERING", enabled = false, frequencyDays = 7))

        val rows = dao.observeForGarden(1).first()
        assertEquals(1, rows.size)
        assertEquals(false, rows[0].enabled)
        assertEquals(7, rows[0].frequencyDays)
    }

    @Test
    fun getEnabled_returnsOnlyEnabledRowsAcrossGardens() = runTest {
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "WATERING", enabled = true))
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "GROWTH", enabled = false))
        dao.upsert(NotificationSettingsEntity(gardenId = 2, type = "PLANTING", enabled = true))

        val enabled = dao.getEnabled()
        assertEquals(2, enabled.size)
        assertTrue(enabled.all { it.enabled })
    }

    @Test
    fun updateLastNotified_setsEpochDay() = runTest {
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "WATERING", enabled = true))
        dao.updateLastNotified(1, "WATERING", 20_000L)

        val row = dao.observeForGarden(1).first().single()
        assertEquals(20_000L, row.lastNotifiedEpochDay)
    }

    @Test
    fun deleteForGarden_removesOnlyThatGarden() = runTest {
        dao.upsert(NotificationSettingsEntity(gardenId = 1, type = "WATERING", enabled = true))
        dao.upsert(NotificationSettingsEntity(gardenId = 2, type = "WATERING", enabled = true))
        dao.deleteForGarden(1)

        assertTrue(dao.observeForGarden(1).first().isEmpty())
        assertEquals(1, dao.observeForGarden(2).first().size)
    }
}
