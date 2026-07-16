package com.gardenapp.e2e

import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/**
 * Builds THE Android run garden through the real UI (list FAB → form → save)
 * and exercises the garden detail screen. Later classes reuse E2e.gardenId;
 * Z99TeardownTest deletes everything.
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class B10GardenBuildTest : ComposeE2eTest() {

    @Test
    fun t1_createGarden_throughForm() {
        val name = E2e.testName("Android Garden")
        navTo("Gardens")
        rule.onNodeWithContentDescription("Add garden").performClick()
        waitForText("Garden Name *")
        type("Garden Name *", name)
        type("Description", "Built by the Android E2E suite")
        type("ZIP Code (US)", "10001")
        type("Water Source", "drip")
        tap("Save", substring = false)

        // Saved → garden detail; resolve the id for the rest of the suite.
        waitForText("View Beds", timeout = loadTimeout)
        val gardens = E2e.getArray("/api/gardens")
        for (i in 0 until gardens.length()) {
            val g = gardens.getJSONObject(i)
            if (g.getString("name") == name) E2e.gardenId = g.getInt("id")
        }
        assertTrue("created garden should be listed by the API", E2e.gardenId != null)
        E2e.logManifest(mapOf("type" to "garden", "id" to E2e.gardenId, "name" to name))
    }

    @Test
    fun t2_gardenList_showsCard_andDetailOpens() {
        navTo("Gardens")
        waitForText(E2e.runId)
        tap(E2e.runId)
        waitForText("View Beds")
        // Detail affordances present.
        waitForText("Garden Journal")
        waitForText("Seed Room")
        waitForText("Compost Helper")
    }

    @Test
    fun t3_bulkCareButtons_recordCare() {
        navTo("Gardens")
        tap(E2e.runId)
        waitForText("View Beds")
        tap("Water All")
        tap("Fertilize")
        tap("Mulch")
        // Bulk care with zero plants still succeeds server-side; the buttons
        // must not crash the screen.
        waitForText("View Beds")
        E2e.logManifest(mapOf("event" to "bulk-care-tapped", "gardenId" to E2e.gardenId))
    }
}
