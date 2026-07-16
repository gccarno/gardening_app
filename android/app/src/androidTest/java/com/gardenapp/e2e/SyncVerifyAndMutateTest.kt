package com.gardenapp.e2e

import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assume.assumeTrue
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/**
 * Cross-platform sync relay, phase 2 of 3 (run by scripts/run_e2e.ps1):
 *
 *   web (Playwright sync-web-mutations) → THIS TEST → web (sync-verify-android)
 *
 * Verifies the web app's changes are visible in the Android UI, then makes
 * Android-side mutations for the web to verify. Skips (Assume) unless the
 * orchestrator passes -e E2E_SYNC_GARDEN_ID <id>.
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class SyncVerifyAndMutateTest : ComposeE2eTest() {

    override fun signIn() {
        assumeTrue("E2E_SYNC_GARDEN_ID not set — sync relay not active", E2e.syncGardenId != null)
        super.signIn()
    }

    private fun gardenName(): String =
        E2e.getObject("/api/gardens/${E2e.syncGardenId}").getString("name")

    @Test
    fun t1_webChanges_visibleInAndroidUi() {
        val name = gardenName() // e.g. "[E2E] <runId> Sync Garden (web edited)"
        navTo("Gardens")
        waitForText(name)          // garden renamed by the web spec appears
        tap(name)
        waitForText("View Beds")

        // Web-created bed, task and journal entry render in their screens.
        tap("View Beds")
        waitForText("Sync Bed")
        Espresso.pressBack() // bed list → garden detail
        Espresso.pressBack() // garden detail → gardens (bottom bar restored)
        navTo("Tasks")
        waitForText("Sync task from web")
        E2e.logManifest(mapOf("event" to "sync-web-changes-verified", "garden" to E2e.syncGardenId))
    }

    @Test
    fun t2_androidMutations_forWebToVerify() {
        val gid = E2e.syncGardenId!!

        // 1. Rename the garden from Android (web verifies the suffix).
        val newName = gardenName().substringBefore(" (web edited)") + " (android edited)"
        E2e.put("/api/gardens/$gid", mapOf("name" to newName))

        // 2. Complete the web's task through the tasks screen endpoint.
        val tasks = E2e.getArray("/api/tasks?garden_id=$gid")
        for (i in 0 until tasks.length()) {
            val t = tasks.getJSONObject(i)
            if (t.getString("title").contains("Sync task from web")) {
                E2e.post("/api/tasks/${t.getInt("id")}/complete")
            }
        }

        // 3. Add a journal entry through the UI.
        navTo("Gardens")
        waitForText(newName)
        tap(newName)
        tap("Garden Journal")
        rule.onAllNodes(hasClickAction().and(hasContentDescription("Add", substring = true)))
            .onFirst().performClick()
        waitForText("Title *")
        type("Title *", "${E2e.PREFIX} Android sync entry")
        tap("Save", substring = false)
        waitForText("Android sync entry")

        // 4. Water the web-planted plant (care date sync check).
        val plants = E2e.getArray("/api/plants?garden_id=$gid")
        if (plants.length() > 0) {
            E2e.post("/api/plants/${plants.getJSONObject(0).getInt("id")}/care",
                mapOf("last_watered" to "2026-07-16", "watering_amount" to "moderate"))
        }
        E2e.logManifest(mapOf("event" to "sync-android-mutations-done", "garden" to gid))
    }
}
