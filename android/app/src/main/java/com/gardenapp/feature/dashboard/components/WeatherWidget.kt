package com.gardenapp.feature.dashboard.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.DailyForecast
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.util.DateUtil
import kotlin.math.roundToInt

@Composable
fun WeatherWidget(weather: WeatherData, modifier: Modifier = Modifier) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            weather.current?.let { current ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text(
                            text = current.temp?.let { "${it.roundToInt()}°F" } ?: "--",
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = current.condition ?: "Unknown",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        current.humidity?.let {
                            Text("Humidity: ${it.roundToInt()}%", style = MaterialTheme.typography.bodySmall)
                        }
                        current.windSpeed?.let {
                            Text("Wind: ${it.roundToInt()} mph", style = MaterialTheme.typography.bodySmall)
                        }
                        current.precipitation?.let {
                            if (it > 0) Text("Precip: ${it}\"", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            weather.frost?.let { frost ->
                HorizontalDivider()
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    frost.lastSpring?.let {
                        Column {
                            Text("Last Frost", style = MaterialTheme.typography.labelSmall)
                            Text(DateUtil.displayDate(it), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                        }
                    }
                    frost.firstFall?.let {
                        Column {
                            Text("First Fall Frost", style = MaterialTheme.typography.labelSmall)
                            Text(DateUtil.displayDate(it), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                        }
                    }
                    frost.frostFree?.let {
                        Column {
                            Text("Frost-Free Days", style = MaterialTheme.typography.labelSmall)
                            Text("$it days", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }

            if (weather.daily.isNotEmpty()) {
                HorizontalDivider()
                Text("7-Day Forecast", style = MaterialTheme.typography.labelMedium)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(weather.daily) { day -> ForecastDayChip(day) }
                }
            }
        }
    }
}

@Composable
private fun ForecastDayChip(day: DailyForecast) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.width(56.dp),
    ) {
        Column(
            modifier = Modifier.padding(6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = shortDayLabel(day.date),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = conditionEmoji(day.condition),
                style = MaterialTheme.typography.titleMedium,
            )
            day.high?.let {
                Text("${it.roundToInt()}°", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
            }
            day.low?.let {
                Text("${it.roundToInt()}°", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

private fun shortDayLabel(dateStr: String): String {
    val date = com.gardenapp.core.util.DateUtil.parseDate(dateStr) ?: return dateStr
    val today = java.time.LocalDate.now()
    return when {
        date == today -> "Today"
        date == today.plusDays(1) -> "Tmrw"
        else -> date.format(java.time.format.DateTimeFormatter.ofPattern("EEE"))
    }
}

private fun conditionEmoji(condition: String?): String = when {
    condition == null -> "🌤"
    condition.contains("rain", ignoreCase = true) -> "🌧"
    condition.contains("snow", ignoreCase = true) -> "❄️"
    condition.contains("thunder", ignoreCase = true) -> "⛈"
    condition.contains("cloud", ignoreCase = true) -> "☁️"
    condition.contains("fog", ignoreCase = true) -> "🌫"
    condition.contains("clear", ignoreCase = true) || condition.contains("sun", ignoreCase = true) -> "☀️"
    condition.contains("partly", ignoreCase = true) -> "⛅"
    else -> "🌤"
}
