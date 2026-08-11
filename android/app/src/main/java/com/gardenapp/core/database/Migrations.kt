package com.gardenapp.core.database

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * Adds the offline caches (dashboard, bed grid, plant detail, scalars).
 *
 * Written as a real migration rather than letting `fallbackToDestructiveMigration`
 * wipe the database: `notification_settings` holds device-local settings that are
 * not re-fetchable — `enabled` is opt-in, so a wipe would silently switch off
 * notifications the user turned on, and losing `lastNotifiedEpochDay` can fire a
 * duplicate reminder.
 *
 * The statements are copied verbatim from `schemas/…/7.json`. Room compares the
 * result against its own expectation and throws if they differ, so do not retype
 * them by hand — regenerate from the exported schema.
 */
val MIGRATION_6_7 = object : Migration(6, 7) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS `dashboard_cache` (`garden_id` INTEGER NOT NULL, `data` TEXT NOT NULL, `fetched_at` INTEGER NOT NULL, PRIMARY KEY(`garden_id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `bed_grid_cache` (`bed_id` INTEGER NOT NULL, `data` TEXT NOT NULL, `fetched_at` INTEGER NOT NULL, PRIMARY KEY(`bed_id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `plant_detail_cache` (`plant_id` INTEGER NOT NULL, `data` TEXT NOT NULL, `fetched_at` INTEGER NOT NULL, PRIMARY KEY(`plant_id`))")
        db.execSQL("CREATE TABLE IF NOT EXISTS `cache_meta` (`cache_key` TEXT NOT NULL, `value` TEXT NOT NULL, `fetched_at` INTEGER NOT NULL, PRIMARY KEY(`cache_key`))")
    }
}
