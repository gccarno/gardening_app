package com.gardenapp

import androidx.room.testing.MigrationTestHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.database.MIGRATION_6_7
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Room throws rather than falling back destructively when a migration exists but
 * leaves the schema in a shape it does not expect, so a typo in MIGRATION_6_7 is a
 * launch crash for every upgrading user. `runMigrationsAndValidate` is that check.
 */
@RunWith(AndroidJUnit4::class)
class MigrationTest {

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        GardenDatabase::class.java,
        emptyList(),
        FrameworkSQLiteOpenHelperFactory(),
    )

    @Test
    fun migrate6To7_matchesRoomsExpectedSchema() {
        helper.createDatabase(TEST_DB, 6).close()

        // Throws if the migration leaves anything Room did not expect.
        helper.runMigrationsAndValidate(TEST_DB, 7, true, MIGRATION_6_7).close()
    }

    @Test
    fun migrate6To7_preservesNotificationSettings() {
        helper.createDatabase(TEST_DB, 6).use { db ->
            db.execSQL(
                "INSERT INTO notification_settings " +
                    "(gardenId, type, enabled, frequencyDays, hourOfDay, lastNotifiedEpochDay) " +
                    "VALUES (1, 'WATERING', 1, 2, 7, 20310)"
            )
        }

        val migrated = helper.runMigrationsAndValidate(TEST_DB, 7, true, MIGRATION_6_7)

        migrated.query("SELECT enabled, hourOfDay, lastNotifiedEpochDay FROM notification_settings").use {
            assertTrue("the opt-in setting must survive the upgrade", it.moveToFirst())
            assertEquals(1, it.getInt(0))
            assertEquals(7, it.getInt(1))
            assertEquals(20310L, it.getLong(2))
        }
        migrated.close()
    }

    companion object {
        private const val TEST_DB = "migration-test.db"
    }
}
