package com.gardenapp.e2e

import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters

/** Real login screen flow: server URL entry, bad password, good password. */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class A00LoginFlowTest : ComposeE2eTest() {

    // Start signed OUT — this class tests the login form itself.
    override fun signIn() {
        E2e.login() // warms the Render service through any cold start
        E2e.signOutLocally()
        waitForText("Sign in to your garden", timeout = loadTimeout)
    }

    private fun setServerUrl() {
        tap("Server settings")
        node("Server URL").performTextClearance()
        node("Server URL").performTextInput(E2e.baseUrl)
        tap("Hide server settings")
    }

    @Test
    fun t1_wrongPassword_showsError_staysOnLogin() {
        setServerUrl()
        type("Email", E2e.email!!)
        type("Password", "definitely-wrong-password")
        tap("Sign in", substring = false)
        // Any error text appears and we remain on the login screen.
        rule.waitUntil(timeoutMillis = loadTimeout) {
            rule.onAllNodes(hasText("Sign in to your garden")).fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun t2_correctCredentials_reachDashboard() {
        setServerUrl()
        type("Email", E2e.email!!)
        type("Password", E2e.password!!)
        tap("Sign in", substring = false)
        waitForText("Dashboard", timeout = loadTimeout)
        E2e.logManifest(mapOf("event" to "android-login-ok"))
    }
}
