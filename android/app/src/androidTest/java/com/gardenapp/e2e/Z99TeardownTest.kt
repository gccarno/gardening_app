package com.gardenapp.e2e

import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/**
 * Deletes everything the Android suite created — children first (garden
 * delete does NOT cascade), then the garden through the real UI delete
 * dialog — and asserts no [E2E] android-run residue remains.
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class Z99TeardownTest : ComposeE2eTest() {

    @Test
    fun t1_deleteChildren_bottomUp_viaApi() {
        val gid = E2e.gardenId
        assumeTrue("no run garden was created (earlier classes failed?)", gid != null)

        val cps = E2e.getArray("/api/gardens/$gid/canvas-plants")
        for (i in 0 until cps.length()) {
            E2e.post("/api/canvas-plants/${cps.getJSONObject(i).getInt("id")}/delete")
        }
        val plants = E2e.getArray("/api/plants?garden_id=$gid")
        for (i in 0 until plants.length()) {
            E2e.delete("/api/plants/${plants.getJSONObject(i).getInt("id")}")
        }
        val beds = E2e.getArray("/api/beds?garden_id=$gid")
        for (i in 0 until beds.length()) {
            E2e.post("/api/beds/${beds.getJSONObject(i).getInt("id")}/delete")
        }
        val tasks = E2e.getArray("/api/tasks?garden_id=$gid")
        for (i in 0 until tasks.length()) {
            E2e.delete("/api/tasks/${tasks.getJSONObject(i).getInt("id")}")
        }
        val journal = E2e.getObject("/api/gardens/$gid/journal?per_page=100").getJSONArray("entries")
        for (i in 0 until journal.length()) {
            E2e.delete("/api/journal/${journal.getJSONObject(i).getInt("id")}")
        }
        val trays = E2e.getArray("/api/gardens/$gid/seed-room")
        for (i in 0 until trays.length()) {
            E2e.delete("/api/seed-room/${trays.getJSONObject(i).getInt("id")}")
        }
        val bins = E2e.getArray("/api/gardens/$gid/compost")
        for (i in 0 until bins.length()) {
            E2e.delete("/api/compost/${bins.getJSONObject(i).getInt("id")}")
        }
        E2e.logManifest(mapOf("event" to "android-children-deleted", "gardenId" to gid))
    }

    @Test
    fun t2_deleteGarden_throughUiDialog() {
        assumeTrue(E2e.gardenId != null)
        navTo("Gardens")
        waitForText(E2e.runId)
        // GardenCard exposes a Delete icon → "Delete Garden" confirm dialog.
        rule.onAllNodes(hasContentDescription("Delete")).onFirst().performClick()
        waitForText("Delete Garden")
        tap("Delete", substring = false)
        waitForTextGone(E2e.runId)
        E2e.logManifest(mapOf("event" to "android-garden-deleted", "gardenId" to E2e.gardenId))
    }

    @Test
    fun t3_noAndroidRunResidue_remains() {
        val gardens = E2e.getArray("/api/gardens")
        var leftovers = 0
        for (i in 0 until gardens.length()) {
            if (gardens.getJSONObject(i).getString("name").contains(E2e.runId)) leftovers++
        }
        assertEquals("gardens from this Android run must be gone", 0, leftovers)
    }
}
