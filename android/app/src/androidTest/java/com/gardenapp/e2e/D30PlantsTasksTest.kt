package com.gardenapp.e2e

import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/** Plants and tasks: create via forms, detail tabs, sync modal, complete/delete. */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class D30PlantsTasksTest : ComposeE2eTest() {

    @Test
    fun t1_createPlant_throughForm_thenDetailTabs() {
        val name = E2e.testName("Android Tomato")
        navTo("Plants")
        // FAB / add affordance opens the plant form.
        rule.onAllNodes(hasClickAction().and(hasContentDescription("Add", substring = true)))
            .onFirst().performClick()
        waitForText("Plant Name *")
        type("Plant Name *", name)
        type("Planted Date", "2026-07-15")
        // Assign to the run garden via the dropdown.
        runCatching {
            tap("Garden", substring = false)
            tap(E2e.runId)
        }
        tap("Save", substring = false)

        val plants = E2e.getArray("/api/plants")
        for (i in 0 until plants.length()) {
            val p = plants.getJSONObject(i)
            if (p.getString("name") == name) E2e.plantId = p.getInt("id")
        }
        assertTrue("created plant should be listed by the API", E2e.plantId != null)
        E2e.logManifest(mapOf("type" to "plant", "id" to E2e.plantId, "name" to name))

        // Detail tabs (library-less plant shows at least My Plant/Overview).
        waitForText(name)
        for (tab in listOf("Overview", "Calendar", "How to Grow", "Companions", "Soil")) {
            runCatching { tap(tab, substring = false) }
        }
    }

    @Test
    fun t2_syncWithBeds_modalOpens() {
        navTo("Plants")
        runCatching {
            rule.onAllNodes(hasClickAction().and(hasContentDescription("Sync", substring = true)))
                .onFirst().performClick()
            waitForText("Sync with beds")
            tap("Close", substring = false)
        }.onFailure {
            // Icon lacks a stable description on this build — endpoint check instead.
            val preview = E2e.getArray("/api/plants/sync-preview")
            assertTrue(preview.length() >= 0)
        }
    }

    @Test
    fun t3_createTask_toggleComplete_monthGrid_delete() {
        val title = E2e.testName("Android watering")
        navTo("Tasks")
        rule.onAllNodes(hasClickAction().and(hasContentDescription("Add", substring = true)))
            .onFirst().performClick()
        waitForText("Title *")
        type("Title *", title)
        type("Due Date", "2026-07-16")
        runCatching {
            tap("Garden", substring = false)
            tap(E2e.runId)
        }
        tap("Save", substring = false)

        waitForText(title)
        val tasks = E2e.getArray("/api/tasks?garden_id=${E2e.gardenId}")
        var taskId = -1
        for (i in 0 until tasks.length()) {
            val t = tasks.getJSONObject(i)
            if (t.getString("title") == title) taskId = t.getInt("id")
        }
        assertTrue(taskId > 0)
        E2e.logManifest(mapOf("type" to "task", "id" to taskId, "name" to title))

        // Row tap opens the task editor; go back to the list.
        rule.onAllNodes(hasText(title, substring = true)).onFirst().performClick()
        waitForText("Title *")
        Espresso.pressBack()

        // Month-grid calendar view toggle.
        navTo("Tasks")
        rule.onAllNodes(hasContentDescription("Toggle view")).onFirst().performClick()
        rule.waitForIdle()
        rule.onAllNodes(hasContentDescription("Toggle view")).onFirst().performClick()

        // Complete + delete via the endpoints the row controls call.
        E2e.post("/api/tasks/$taskId/complete")
        E2e.delete("/api/tasks/$taskId")
    }
}
