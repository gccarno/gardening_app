package com.gardenapp.core.ui.components

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.gardenapp.core.util.DateUtil

/**
 * Says how old the content on screen is, so cached data is never mistaken for live
 * data. Renders nothing until something has actually been cached.
 *
 * Keys off [refreshFailed] rather than connectivity: the app-wide OfflineBanner
 * already covers "no network", and a refresh can equally fail against a sleeping
 * server while the device is perfectly online.
 */
@Composable
fun CacheStatusLine(
    fetchedAt: Long?,
    isRefreshing: Boolean,
    refreshFailed: Boolean,
    modifier: Modifier = Modifier,
) {
    val at = fetchedAt ?: return
    val text = when {
        isRefreshing -> "Updating…"
        refreshFailed -> "Offline — showing saved data"
        else -> "Updated ${DateUtil.relativeSince(at)}"
    }
    Text(
        text = text,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier,
    )
}
