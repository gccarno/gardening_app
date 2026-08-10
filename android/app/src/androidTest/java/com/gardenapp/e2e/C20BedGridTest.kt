package com.gardenapp.e2e

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/**
 * Beds on Android: create through the form (all soil fields), then drive the bed
 * grid the way a user does — tap an empty cell to place a plant, tap the plant to
 * log care, long press to remove.
 *
 * Placement goes through the real UI. An earlier version of this test called the
 * grid-plant API directly because the canvas had no per-cell semantics; that let a
 * bug where grid taps did nothing at all pass CI. Cells now carry testTags
 * (`bed-cell-<col>-<row>`), so a broken tap handler fails the suite.
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class C20BedGridTest : ComposeE2eTest() {

    private fun openBedList() {
        navTo("Gardens")
        tap(E2e.runId)
        tap("View Beds")
    }

    private fun openBed() {
        openBedList()
        tap(E2e.runId)
    }

    /** Bed plants currently placed on the grid, per the API. */
    private fun placedNames(): List<String> {
        val grid = E2e.getObject("/api/beds/${E2e.bedId}/grid")
        val placed = grid.getJSONArray("placed")
        return (0 until placed.length()).map { placed.getJSONObject(it).getString("plant_name") }
    }

    @Test
    fun t1_createBed_withSoilProfile() {
        val name = E2e.testName("Android Bed")
        openBedList()
        // Empty state has "Add First Bed"; otherwise a FAB/add affordance.
        runCatching { tap("Add First Bed") }.onFailure { tap("Add") }
        waitForText("Bed Name *")
        type("Bed Name *", name)
        type("Soil Notes", "Sandy loam, amended with compost")
        type("pH", "6.5")
        type("Clay", "20")
        type("Compost", "50")
        type("Sand", "30")
        tap("Save", substring = false)

        // Saved → bed detail. Resolve id via API.
        val beds = E2e.getArray("/api/beds?garden_id=${E2e.gardenId}")
        for (i in 0 until beds.length()) {
            val b = beds.getJSONObject(i)
            if (b.getString("name") == name) E2e.bedId = b.getInt("id")
        }
        assertTrue("created bed should be listed by the API", E2e.bedId != null)
        E2e.logManifest(mapOf("type" to "bed", "id" to E2e.bedId, "name" to name))

        // The soil profile must survive the create call, not just an edit.
        val bed = E2e.getObject("/api/beds/${E2e.bedId}")
        assertEquals(6.5, bed.getDouble("soil_ph"), 0.01)
        assertEquals("Sandy loam, amended with compost", bed.optString("soil_notes"))
        assertEquals(20.0, bed.getDouble("clay_pct"), 0.01)
    }

    @Test
    fun t2_tappingEmptyCell_placesPlantFromPicker() {
        openBed()

        // Tap the top-left cell → plant picker → choose a tomato.
        tapTag("bed-cell-0-0")
        waitForText("Choose a Plant")
        type("Search plants…", "Tomato")
        waitForText("Tomato")
        tap("Tomato")

        // A crop-rotation conflict is possible on a re-run; accept it and plant anyway.
        runCatching { tap("Plant anyway") }

        rule.waitUntil(timeoutMillis = loadTimeout) { placedNames().isNotEmpty() }
        assertTrue(
            "tapping an empty cell should place a plant, got ${placedNames()}",
            placedNames().any { it.contains("Tomato", ignoreCase = true) },
        )
        E2e.logManifest(mapOf("type" to "bed_plant", "bed_id" to E2e.bedId))
    }

    @Test
    fun t3_tappingPlant_savesFullCareRecord() {
        openBed()
        waitForTag("bed-cell-0-0")

        // Tap the placed plant → care sheet.
        tapTag("bed-cell-0-0")
        waitForText("Care Log")

        // Dates come from the picker now, not free text.
        tap("Today", substring = false)          // Last Watered = today
        tapTag("stage-dropdown")
        tap("Harvesting", substring = false)
        type("Health Notes", "E2E: healthy, new growth")
        tap("Save Care")

        waitForTextGone("Care Log")

        val bpId = E2e.getObject("/api/beds/${E2e.bedId}/grid")
            .getJSONArray("placed").getJSONObject(0).getInt("id")
        val bp = E2e.getObject("/api/bedplants/$bpId")
        assertEquals("harvesting", bp.optString("stage"))
        assertTrue("watering date should be set", bp.optString("last_watered").isNotBlank())
        assertTrue(bp.optString("health_notes").contains("E2E"))
    }

    @Test
    fun t4_longPressPlant_removesItAfterConfirm() {
        openBed()
        waitForTag("bed-cell-0-0")
        assertTrue("plant should be present before removal", placedNames().isNotEmpty())

        longPressTag("bed-cell-0-0")
        waitForText("Remove Plant")
        tap("Remove", substring = false)

        rule.waitUntil(timeoutMillis = loadTimeout) { placedNames().isEmpty() }
        assertFalse("long press + confirm should remove the plant", placedNames().isNotEmpty())
    }

    @Test
    fun t5_rotationWarnings_loadOnBedDetail() {
        openBed()
        // The rotation-warnings endpoint feeds a card on this screen; assert
        // it answers for this bed (UI text varies with family data).
        val warnings = E2e.getObject("/api/beds/${E2e.bedId}/rotation-warnings")
        assertTrue(warnings.has("families_in_bed"))
    }
}
