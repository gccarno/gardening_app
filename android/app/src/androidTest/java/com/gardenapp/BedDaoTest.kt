package com.gardenapp

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.database.entities.BedEntity
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class BedDaoTest {

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
    fun upsertAndReadBeds() = runTest {
        db.bedDao().upsertBeds(listOf(
            BedEntity(id = 1, name = "Raised Bed", gardenId = 10, widthFt = 4f, heightFt = 8f),
            BedEntity(id = 2, name = "Container", gardenId = 10, widthFt = 2f, heightFt = 2f),
        ))

        val result = db.bedDao().getAllBeds().first()
        assertEquals(2, result.size)
    }

    @Test
    fun getBedsByGarden_filtersCorrectly() = runTest {
        db.bedDao().upsertBeds(listOf(
            BedEntity(id = 1, name = "Bed A", gardenId = 1),
            BedEntity(id = 2, name = "Bed B", gardenId = 2),
            BedEntity(id = 3, name = "Bed C", gardenId = 1),
        ))

        val result = db.bedDao().getBedsByGarden(1).first()
        assertEquals(2, result.size)
        assert(result.all { it.gardenId == 1 })
    }

    @Test
    fun getBed_returnsCorrectBed() = runTest {
        db.bedDao().upsertBed(BedEntity(id = 7, name = "Herb Spiral", gardenId = 3,
            widthFt = 3f, heightFt = 3f, soilPh = 6.5f))

        val result = db.bedDao().getBed(7)
        assertEquals("Herb Spiral", result?.name)
        assertEquals(6.5f, result?.soilPh)
    }

    @Test
    fun getBed_returnsNullForMissing() = runTest {
        val result = db.bedDao().getBed(999)
        assertNull(result)
    }

    @Test
    fun deleteBed_removesOnlyTargeted() = runTest {
        db.bedDao().upsertBeds(listOf(
            BedEntity(id = 1, name = "Keep", gardenId = 1),
            BedEntity(id = 2, name = "Remove", gardenId = 1),
        ))
        db.bedDao().deleteBed(2)

        val result = db.bedDao().getAllBeds().first()
        assertEquals(1, result.size)
        assertEquals(1, result[0].id)
    }

    @Test
    fun deleteBedsByGarden_removesAllForGarden() = runTest {
        db.bedDao().upsertBeds(listOf(
            BedEntity(id = 1, name = "A", gardenId = 1),
            BedEntity(id = 2, name = "B", gardenId = 1),
            BedEntity(id = 3, name = "C", gardenId = 2),
        ))
        db.bedDao().deleteBedsByGarden(1)

        val result = db.bedDao().getAllBeds().first()
        assertEquals(1, result.size)
        assertEquals(2, result[0].gardenId)
    }

    @Test
    fun upsertBed_updatesExisting() = runTest {
        db.bedDao().upsertBed(BedEntity(id = 1, name = "Old", gardenId = 1, widthFt = 4f, heightFt = 8f))
        db.bedDao().upsertBed(BedEntity(id = 1, name = "Updated", gardenId = 1, widthFt = 6f, heightFt = 8f))

        val result = db.bedDao().getBed(1)
        assertEquals("Updated", result?.name)
        assertEquals(6f, result?.widthFt)
    }
}
