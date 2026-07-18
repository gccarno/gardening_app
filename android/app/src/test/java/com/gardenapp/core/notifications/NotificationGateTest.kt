package com.gardenapp.core.notifications

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationGateTest {

    private val today = 20_000L  // arbitrary epoch day

    @Test
    fun `never notified fires once past the configured hour`() {
        assertTrue(shouldNotify(nowHour = 8, hourOfDay = 8, todayEpochDay = today,
            lastNotifiedEpochDay = null, frequencyDays = 1))
    }

    @Test
    fun `blocked before the configured hour`() {
        assertFalse(shouldNotify(nowHour = 7, hourOfDay = 8, todayEpochDay = today,
            lastNotifiedEpochDay = null, frequencyDays = 1))
    }

    @Test
    fun `blocked when already notified today`() {
        assertFalse(shouldNotify(nowHour = 15, hourOfDay = 8, todayEpochDay = today,
            lastNotifiedEpochDay = today, frequencyDays = 1))
    }

    @Test
    fun `daily frequency fires again the next day`() {
        assertTrue(shouldNotify(nowHour = 8, hourOfDay = 8, todayEpochDay = today,
            lastNotifiedEpochDay = today - 1, frequencyDays = 1))
    }

    @Test
    fun `weekly frequency blocks until seven days have passed`() {
        assertFalse(shouldNotify(nowHour = 8, hourOfDay = 8, todayEpochDay = today,
            lastNotifiedEpochDay = today - 6, frequencyDays = 7))
        assertTrue(shouldNotify(nowHour = 8, hourOfDay = 8, todayEpochDay = today,
            lastNotifiedEpochDay = today - 7, frequencyDays = 7))
    }
}
