package com.gardenapp.core.notifications

/**
 * Decides whether a per-garden notification type may fire on this worker run:
 * not before the configured hour, and at most once every [frequencyDays].
 */
fun shouldNotify(
    nowHour: Int,
    hourOfDay: Int,
    todayEpochDay: Long,
    lastNotifiedEpochDay: Long?,
    frequencyDays: Int,
): Boolean =
    nowHour >= hourOfDay &&
        (lastNotifiedEpochDay == null ||
            todayEpochDay - lastNotifiedEpochDay >= frequencyDays)
