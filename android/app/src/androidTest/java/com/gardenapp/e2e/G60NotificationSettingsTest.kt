package com.gardenapp.e2e

import android.Manifest
import android.os.Build
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.rule.GrantPermissionRule
import org.junit.FixMethodOrder
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestRule
import org.junit.rules.RuleChain
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/**
 * Per-garden notification settings: toggle a type on, change frequency,
 * reopen and assert persistence (Room-backed, device-local).
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class G60NotificationSettingsTest : ComposeE2eTest() {

    // Pre-grant POST_NOTIFICATIONS so the runtime prompt (API 33+) never blocks
    // the toggle; on older APIs the permission doesn't exist, so grant nothing.
    @get:Rule
    val permissionRule: TestRule =
        if (Build.VERSION.SDK_INT >= 33) {
            GrantPermissionRule.grant(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            RuleChain.emptyRuleChain()
        }

    private fun openNotificationSettings() {
        navTo("Gardens")
        tap(E2e.runId)
        rule.onNodeWithContentDescription("Notification Settings").performClick()
        rule.waitForIdle()
        waitForText("Watering reminders")
    }

    @Test
    fun t1_toggleWateringOn_setWeekly() {
        openNotificationSettings()
        rule.onNodeWithTag("notif-switch-watering").performClick()
        rule.waitForIdle()
        waitForText("Frequency")
        rule.onNodeWithTag("notif-freq-watering-7").performScrollTo().performClick()
        rule.waitForIdle()
        E2e.logManifest(mapOf("event" to "notification-settings-saved"))
    }

    @Test
    fun t2_settingsPersistAcrossReopen() {
        openNotificationSettings()
        rule.onNodeWithTag("notif-freq-watering-7").performScrollTo().assertIsSelected()
        // Leave things as we found them: toggle watering back off.
        rule.onNodeWithTag("notif-switch-watering").performClick()
        rule.waitForIdle()
    }
}
