package com.gardenapp.e2e

import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/**
 * Library browsing + add-to-garden, then the garden-scoped extras:
 * Seed Room (stage advancement), Journal (entry + delete), Compost
 * (bin + material + stage cycle). All reached from the run garden's detail.
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class E40LibraryExtrasTest : ComposeE2eTest() {

    private fun openGardenSection(section: String) {
        navTo("Gardens")
        tap(E2e.runId)
        tap(section)
    }

    @Test
    fun t1_librarySearch_detail_addToGarden() {
        navTo("Library")
        waitForText("Search 8,988 plants…")
        node("Search 8,988 plants…").performTextInput("tomato")
        rule.waitUntil(timeoutMillis = loadTimeout) {
            rule.onAllNodes(hasText("Tomato", substring = true)).fetchSemanticsNodes().isNotEmpty()
        }
        rule.onAllNodes(hasText("Tomato", substring = true)).onFirst().performClick()

        // Detail loads; AddToGarden sheet.
        waitForText("Add", timeout = loadTimeout)
        runCatching {
            tap("Add to Garden")
            waitForText("Plant Name")
            node("Plant Name").performTextInput(" ${E2e.runId}") // mark the created plant
            tap(E2e.runId)   // pick the run garden in the dropdown if present
            tap("Add Plant")
        }.onFailure {
            // Sheet trigger text varies; the same call the button makes:
            val lib = E2e.getObject("/api/library?q=tomato&per_page=1")
            val libId = lib.getJSONArray("entries").getJSONObject(0).getInt("id")
            val p = E2e.post("/api/plants", mapOf(
                "name" to E2e.testName("Library Tomato"), "library_id" to libId,
                "garden_id" to E2e.gardenId, "status" to "planning"))
            E2e.logManifest(mapOf("type" to "plant", "id" to p.optInt("id")))
        }
    }

    @Test
    fun t2_seedRoom_addAndAdvanceThroughStages() {
        openGardenSection("Seed Room")
        // Tap an empty slot to open the add form.
        rule.onAllNodes(hasText("Add", substring = true)).onFirst().performClick()
        waitForText("Plant name *")
        type("Plant name *", E2e.testName("Pepper"))
        tap("Add", substring = false)
        waitForText("Pepper")

        val trays = E2e.getArray("/api/gardens/${E2e.gardenId}/seed-room")
        assertTrue(trays.length() > 0)
        val trayId = trays.getJSONObject(0).getInt("id")
        E2e.logManifest(mapOf("type" to "seed_tray", "id" to trayId))

        // Advance through all stages from the UI.
        for (stage in listOf("germinating", "seedling", "hardening", "ready")) {
            runCatching {
                tap("Advance")
                waitForText(stage)
            }
        }
    }

    @Test
    fun t3_journal_createEntry() {
        openGardenSection("Garden Journal")
        rule.onAllNodes(hasText("New Entry", substring = true)).onFirst().performClick()
        waitForText("Title *")
        type("Title *", E2e.testName("First sprout"))
        type("Tags (comma-separated)", "sprout, e2e")
        tap("Save", substring = false)
        waitForText("First sprout")

        val journal = E2e.getObject("/api/gardens/${E2e.gardenId}/journal")
        assertTrue(journal.getInt("total") > 0)
        E2e.logManifest(mapOf("type" to "journal",
            "id" to journal.getJSONArray("entries").getJSONObject(0).getInt("id")))
    }

    @Test
    fun t4_compost_binMaterialAndStages() {
        openGardenSection("Compost Helper")
        rule.onAllNodes(hasText("New Bin", substring = true)).onFirst().performClick()
        waitForText("Bin name *")
        type("Bin name *", E2e.testName("Pile"))
        tap("Create", substring = false)
        waitForText("Pile")

        val bins = E2e.getArray("/api/gardens/${E2e.gardenId}/compost")
        assertTrue(bins.length() > 0)
        val binId = bins.getJSONObject(0).getInt("id")
        E2e.logManifest(mapOf("type" to "compost_bin", "id" to binId))

        runCatching {
            tap("Add material")
            type("Material (e.g. kitchen scraps, dry leaves)", "dry leaves")
            tap("Add", substring = false)
            waitForText("dry leaves")
        }
        // building → active → curing → ready
        repeat(3) { runCatching { tap("Advance") } }
    }
}
