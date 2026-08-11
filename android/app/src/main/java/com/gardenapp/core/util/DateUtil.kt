package com.gardenapp.core.util

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.time.temporal.ChronoUnit

object DateUtil {
    private val isoFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    fun parseDate(dateStr: String?): LocalDate? = dateStr?.let {
        try { LocalDate.parse(it, isoFormatter) } catch (e: DateTimeParseException) { null }
    }

    fun formatDate(date: LocalDate): String = date.format(isoFormatter)

    fun daysUntil(dateStr: String?): Long? {
        val date = parseDate(dateStr) ?: return null
        return ChronoUnit.DAYS.between(LocalDate.now(), date)
    }

    fun displayDate(dateStr: String?): String {
        val date = parseDate(dateStr) ?: return dateStr ?: ""
        return date.format(DateTimeFormatter.ofPattern("MMM d, yyyy"))
    }

    /** How long ago a cache entry was written, e.g. "just now", "5m ago", "2h ago". */
    fun relativeSince(epochMillis: Long, now: Long = System.currentTimeMillis()): String {
        val seconds = ((now - epochMillis) / 1000).coerceAtLeast(0)
        return when {
            seconds < 60 -> "just now"
            seconds < 3600 -> "${seconds / 60}m ago"
            seconds < 86_400 -> "${seconds / 3600}h ago"
            else -> "${seconds / 86_400}d ago"
        }
    }

    fun relativeDate(dateStr: String?): String {
        val date = parseDate(dateStr) ?: return dateStr ?: ""
        val days = ChronoUnit.DAYS.between(LocalDate.now(), date)
        return when {
            days == 0L -> "Today"
            days == 1L -> "Tomorrow"
            days == -1L -> "Yesterday"
            days > 1 -> "In $days days"
            else -> "${-days} days ago"
        }
    }
}
