package com.gardenapp.e2e

import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.hasText
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

/**
 * Base for the live-backend instrumented suite. Signs the app in (DataStore
 * token + server URL) before each test; MainActivity reacts to the DataStore
 * flow, so the nav graph appears without touching the login form.
 */
abstract class ComposeE2eTest {

    @get:Rule
    val rule: AndroidComposeTestRule<*, MainActivity> = createAndroidComposeRule<MainActivity>()

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

    /** Fill an OutlinedTextField found by its label text. */
    protected fun type(label: String, value: String) {
        waitForText(label)
        runCatching { node(label).performScrollTo() }
        node(label).performClick()
        node(label).performTextInput(value)
        rule.waitForIdle()
    }

    protected fun navTo(tab: String) {
        tap(tab, substring = false)
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
