package com.gardenapp

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.database.entities.GardenEntity
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class GardenDaoTest {

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
    fun upsertAndReadGardens() = runTest {
        val gardens = listOf(
            GardenEntity(id = 1, name = "Backyard"),
            GardenEntity(id = 2, name = "Front Yard"),
        )
        db.gardenDao().upsertGardens(gardens)

        val result = db.gardenDao().getAllGardens().first()
        assertEquals(2, result.size)
        assertEquals("Backyard", result.find { it.id == 1 }?.name)
    }

    @Test
    fun getById_returnsCorrectGarden() = runTest {
        db.gardenDao().upsertGarden(GardenEntity(id = 5, name = "Herb Garden", zipCode = "90210"))

        val result = db.gardenDao().getGarden(5)
        assertEquals("Herb Garden", result?.name)
        assertEquals("90210", result?.zipCode)
    }

    @Test
    fun getById_returnsNullForMissingId() = runTest {
        val result = db.gardenDao().getGarden(999)
        assertNull(result)
    }

    @Test
    fun upsertOverwritesExisting() = runTest {
        db.gardenDao().upsertGarden(GardenEntity(id = 1, name = "Old Name"))
        db.gardenDao().upsertGarden(GardenEntity(id = 1, name = "New Name"))

        val result = db.gardenDao().getAllGardens().first()
        assertEquals(1, result.size)
        assertEquals("New Name", result[0].name)
    }

    @Test
    fun deleteGarden_removesOnlyTargeted() = runTest {
        db.gardenDao().upsertGardens(listOf(
            GardenEntity(id = 1, name = "Keep"),
            GardenEntity(id = 2, name = "Delete Me"),
        ))
        db.gardenDao().deleteGarden(2)

        val result = db.gardenDao().getAllGardens().first()
        assertEquals(1, result.size)
        assertEquals(1, result[0].id)
    }

    @Test
    fun deleteAll_clearsTable() = runTest {
        db.gardenDao().upsertGardens(listOf(
            GardenEntity(id = 1, name = "A"),
            GardenEntity(id = 2, name = "B"),
        ))
        db.gardenDao().deleteAll()

        val result = db.gardenDao().getAllGardens().first()
        assertEquals(0, result.size)
    }
}
