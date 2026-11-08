package com.gardenapp.e2e

import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isSelectable
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.printToLog
import androidx.compose.ui.test.junit4.AndroidComposeTestRule
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTouchInput
import com.gardenapp.MainActivity
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Rule
import org.junit.rules.TestWatcher
import org.junit.runner.Description

/**
 * Base for the live-backend instrumented suite. Signs the app in (DataStore
 * token + server URL) before each test; MainActivity reacts to the DataStore
 * flow, so the nav graph appears without touching the login form.
 */
abstract class ComposeE2eTest {

    @get:Rule(order = 0)
    val rule: AndroidComposeTestRule<*, MainActivity> = createAndroidComposeRule<MainActivity>()

    /** On failure, dump the semantics tree to logcat (tag E2E_TREE) so a
     *  selector miss shows what was actually on screen. Inner to [rule]
     *  (higher order) so the activity is still alive when it runs. */
    @get:Rule(order = 1)
    val dumpTreeOnFailure = object : TestWatcher() {
        override fun failed(e: Throwable?, description: Description?) {
            runCatching { rule.onRoot().printToLog("E2E_TREE") }
        }
    }

    /** Generous: Render free tier + Neon round trips. */
    protected val loadTimeout = 60_000L

    @Before
    open fun signIn() {
        E2e.ensureSignedIn()
        waitForText("Dashboard", timeout = loadTimeout)
    }

    protected fun waitForText(text: String, substring: Boolean = true, timeout: Long = loadTimeout) {
        rule.waitUntil(timeoutMillis = timeout) {
            rule.onAllNodes(hasText(text, substring = substring)).fetchSemanticsNodes().isNotEmpty()
        }
    }

    protected fun waitForTextGone(text: String, timeout: Long = loadTimeout) {
        rule.waitUntil(timeoutMillis = timeout) {
            rule.onAllNodes(hasText(text, substring = true)).fetchSemanticsNodes().isEmpty()
        }
    }

    private fun isShown(text: String, substring: Boolean = true) =
        rule.onAllNodes(hasText(text, substring = substring)).fetchSemanticsNodes().isNotEmpty()

    /**
     * Wait for a form save to navigate to [successText]. Unlike a bare
     * [waitForText], this fails fast with a diagnostic when the save errors
     * instead of hanging the full timeout: a failed save keeps us on the form
     * (its [formTitle] still shown and the "Save" button back from its saving
     * spinner), which we detect and report — enriched by [diagnose], e.g. an
     * API cross-check. The usual culprit is a backend 5xx (connection-pool
     * exhaustion), which otherwise surfaces as an opaque ComposeTimeoutException.
     */
    protected fun waitForSavedNavigation(
        successText: String,
        formTitle: String,
        timeout: Long = loadTimeout,
        diagnose: () -> String = { "" },
    ) {
        var sawSaving = false
        runCatching {
            rule.waitUntil(timeoutMillis = timeout) {
                if (!isShown("Save", substring = false) && isShown(formTitle)) sawSaving = true
                isShown(successText) ||
                    (sawSaving && isShown(formTitle) && isShown("Save", substring = false))
            }
        }
        if (isShown(successText)) return
        fail(
            "Save did not reach \"$successText\" within ${timeout}ms " +
                "(stillOnForm=${isShown(formTitle)}). ${diagnose()}".trim()
        )
    }

    protected fun node(text: String, substring: Boolean = true): SemanticsNodeInteraction =
        rule.onNodeWithText(text, substring = substring)

    protected fun tap(text: String, substring: Boolean = true) {
        waitForText(text, substring)
        runCatching { node(text, substring).performScrollTo() }
        node(text, substring).performClick()
        rule.waitForIdle()
    }

    /** Fill an OutlinedTextField found by its label text. Pass substring=false
     *  when the label is a prefix of another field's text (e.g. "Sand" vs a
     *  Soil Notes value of "Sandy loam"). */
    protected fun type(label: String, value: String, substring: Boolean = true) {
        waitForText(label, substring)
        runCatching { node(label, substring).performScrollTo() }
        node(label, substring).performClick()
        node(label, substring).performTextInput(value)
        rule.waitForIdle()
    }

    /**
     * Tap a button or menu item by its text, skipping text fields and plain
     * labels. Needed wherever the same text also appears in a title or in a
     * field: a form titled "Add Plant" with an "Add Plant" button, or a
     * dropdown item named after the run ID while a field holds a name that
     * contains it.
     */
    protected fun tapClickable(text: String, substring: Boolean = true) {
        val matcher = hasText(text, substring = substring)
            .and(hasClickAction()).and(hasSetTextAction().not())
        rule.waitUntil(timeoutMillis = loadTimeout) {
            rule.onAllNodes(matcher).fetchSemanticsNodes().isNotEmpty()
        }
        // Scroll first: a click on an off-screen button (e.g. the save button at
        // the bottom of a long form) injects a touch that lands on nothing.
        runCatching { rule.onAllNodes(matcher).onFirst().performScrollTo() }
        rule.onAllNodes(matcher).onFirst().performClick()
        rule.waitForIdle()
    }

    /**
     * Gardens tab → this run's garden detail. Retries the card tap once: a tap
     * that lands while the list is still refreshing can leave us on the list
     * (seen on the planner test). "View Beds" marks the detail screen.
     */
    protected fun openRunGarden() {
        navTo("Gardens")
        tap(E2e.runId)
        runCatching { waitForText("View Beds", timeout = 15_000) }.onFailure {
            tap(E2e.runId)
            waitForText("View Beds")
        }
    }

    /** Wait for any node containing [text], then tap the first one. */
    protected fun tapFirst(text: String) {
        waitForText(text)
        rule.onAllNodes(hasText(text, substring = true)).onFirst().performClick()
        rule.waitForIdle()
    }

    /** Bottom-nav tab. Matched as a selectable node because the dashboard's
     *  metric cards repeat "Plants" and "Tasks". */
    protected fun navTo(tab: String) {
        val matcher = hasText(tab, substring = false).and(isSelectable())
        rule.waitUntil(timeoutMillis = loadTimeout) {
            rule.onAllNodes(matcher).fetchSemanticsNodes().isNotEmpty()
        }
        rule.onAllNodes(matcher).onFirst().performClick()
        rule.waitForIdle()
    }

    // ── Test-tag interactions ────────────────────────────────────────────────
    // The bed grid draws itself on a canvas, so its cells carry testTags rather
    // than text. These let a test tap a real cell instead of calling the API.

    protected fun waitForTag(tag: String, timeout: Long = loadTimeout) {
        rule.waitUntil(timeoutMillis = timeout) {
            rule.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty()
        }
    }

    protected fun tapTag(tag: String) {
        waitForTag(tag)
        runCatching { rule.onNodeWithTag(tag).performScrollTo() }
        rule.onNodeWithTag(tag).performClick()
        rule.waitForIdle()
    }

    protected fun longPressTag(tag: String) {
        waitForTag(tag)
        runCatching { rule.onNodeWithTag(tag).performScrollTo() }
        rule.onNodeWithTag(tag).performTouchInput { longClick() }
        rule.waitForIdle()
    }

    /** Tap a node by its contentDescription (icon buttons). */
    protected fun tapDescription(description: String) {
        rule.waitUntil(timeoutMillis = loadTimeout) {
            rule.onAllNodesWithContentDescription(description).fetchSemanticsNodes().isNotEmpty()
        }
        rule.onNodeWithContentDescription(description).performClick()
        rule.waitForIdle()
    }
}
