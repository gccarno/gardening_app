package com.gardenapp.core.util

import org.junit.Assert.assertEquals
import org.junit.Test

class DateUtilTest {

    private val now = 1_000_000_000L

    private fun since(secondsAgo: Long) =
        DateUtil.relativeSince(now - secondsAgo * 1000L, now)

    @Test
    fun underAMinuteReadsAsJustNow() {
        assertEquals("just now", since(0))
        assertEquals("just now", since(59))
    }

    @Test
    fun minutesUpToAnHour() {
        assertEquals("1m ago", since(60))
        assertEquals("59m ago", since(3599))
    }

    @Test
    fun hoursUpToADay() {
        assertEquals("1h ago", since(3600))
        assertEquals("2h ago", since(7200))
        assertEquals("23h ago", since(86_399))
    }

    @Test
    fun daysBeyondThat() {
        assertEquals("1d ago", since(86_400))
        assertEquals("3d ago", since(3 * 86_400))
    }

    @Test
    fun aClockSkewedFutureTimestampDoesNotReadAsNegative() {
        assertEquals("just now", DateUtil.relativeSince(now + 60_000L, now))
    }
}
