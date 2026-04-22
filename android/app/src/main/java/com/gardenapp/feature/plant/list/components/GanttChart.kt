package com.gardenapp.feature.plant.list.components

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gardenapp.core.model.Plant
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.roundToInt

private val MONTH_LABELS = listOf("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
private const val WEEKS_TOTAL = 52
private const val HEADER_HEIGHT_DP = 32
private const val ROW_HEIGHT_DP = 36
private const val LABEL_WIDTH_DP = 120
private const val WEEK_WIDTH_DP = 28

@Composable
fun GanttChart(
    plants: List<Plant>,
    lastFrostDate: String?,
    firstFrostDate: String?,
    modifier: Modifier = Modifier,
) {
    val today = remember { LocalDate.now() }
    // Week 0 = Jan 1 of current year
    val yearStart = remember { LocalDate.of(today.year, 1, 1) }

    val textMeasurer = rememberTextMeasurer()
    val colorScheme = MaterialTheme.colorScheme

    val totalHeightDp = HEADER_HEIGHT_DP + plants.size * ROW_HEIGHT_DP

    Row(modifier = modifier) {
        // Fixed label column
        Column(modifier = Modifier.width(LABEL_WIDTH_DP.dp)) {
            Spacer(Modifier.height(HEADER_HEIGHT_DP.dp))
            plants.forEach { plant ->
                Box(modifier = Modifier.height(ROW_HEIGHT_DP.dp).fillMaxWidth()) {
                    Text(
                        text = plant.name.take(16),
                        style = MaterialTheme.typography.labelSmall,
                        maxLines = 1,
                        modifier = Modifier.padding(start = 4.dp, top = 4.dp),
                    )
                }
            }
        }

        // Scrollable chart area
        Box(
            modifier = Modifier
                .horizontalScroll(rememberScrollState())
                .width((WEEKS_TOTAL * WEEK_WIDTH_DP).dp)
                .height(totalHeightDp.dp)
                .drawWithCache {
                    val weekPx = WEEK_WIDTH_DP.dp.toPx()
                    val rowPx = ROW_HEIGHT_DP.dp.toPx()
                    val headerPx = HEADER_HEIGHT_DP.dp.toPx()

                    // Pre-compute frost week offsets
                    val lastFrostWeek = lastFrostDate?.let { parseFrostWeek(it, yearStart) }
                    val firstFrostWeek = firstFrostDate?.let { parseFrostWeek(it, yearStart) }
                    val todayWeek = ChronoUnit.WEEKS.between(yearStart, today).toFloat()

                    onDrawBehind {
                        // Draw month header lines and labels
                        drawMonthHeaders(textMeasurer, yearStart, weekPx, headerPx)

                        // Draw alternating row backgrounds
                        plants.forEachIndexed { i, _ ->
                            if (i % 2 == 1) {
                                drawRect(
                                    color = Color(0x0A000000),
                                    topLeft = Offset(0f, headerPx + i * rowPx),
                                    size = Size(size.width, rowPx),
                                )
                            }
                        }

                        // Draw today line
                        val todayX = todayWeek * weekPx
                        drawLine(
                            color = Color(0x88FF5722.toInt()),
                            start = Offset(todayX, 0f),
                            end = Offset(todayX, size.height),
                            strokeWidth = 2.dp.toPx(),
                        )

                        // Draw frost lines
                        val dashEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 4f), 0f)
                        lastFrostWeek?.let { week ->
                            drawLine(
                                color = Color(0xBB2196F3.toInt()),
                                start = Offset(week * weekPx, 0f),
                                end = Offset(week * weekPx, size.height),
                                strokeWidth = 1.5.dp.toPx(),
                                pathEffect = dashEffect,
                            )
                        }
                        firstFrostWeek?.let { week ->
                            drawLine(
                                color = Color(0xBBFF9800.toInt()),
                                start = Offset(week * weekPx, 0f),
                                end = Offset(week * weekPx, size.height),
                                strokeWidth = 1.5.dp.toPx(),
                                pathEffect = dashEffect,
                            )
                        }

                        // Draw plant bars
                        plants.forEachIndexed { i, plant ->
                            val barTop = headerPx + i * rowPx + rowPx * 0.2f
                            val barHeight = rowPx * 0.6f
                            drawPlantBar(plant, yearStart, weekPx, barTop, barHeight)
                        }
                    }
                },
        )
    }
}

private fun parseFrostWeek(dateStr: String, yearStart: LocalDate): Float {
    return try {
        val parts = dateStr.split("-")
        val date = when (parts.size) {
            3 -> LocalDate.parse(dateStr)
            2 -> LocalDate.of(yearStart.year, parts[0].toInt(), parts[1].toInt())
            else -> return -1f
        }
        ChronoUnit.WEEKS.between(yearStart, date).toFloat()
    } catch (e: Exception) {
        -1f
    }
}

private fun DrawScope.drawMonthHeaders(
    textMeasurer: TextMeasurer,
    yearStart: LocalDate,
    weekPx: Float,
    headerPx: Float,
) {
    val labelStyle = TextStyle(fontSize = 9.sp, color = Color(0xFF666666))
    for (month in 1..12) {
        val monthStart = LocalDate.of(yearStart.year, month, 1)
        val weekOffset = ChronoUnit.WEEKS.between(yearStart, monthStart).toFloat()
        val x = weekOffset * weekPx
        drawLine(
            color = Color(0x33000000),
            start = Offset(x, 0f),
            end = Offset(x, headerPx),
            strokeWidth = 1f,
        )
        drawText(
            textMeasurer = textMeasurer,
            text = MONTH_LABELS[month - 1],
            topLeft = Offset(x + 2f, headerPx * 0.2f),
            style = labelStyle,
        )
    }
}

private fun DrawScope.drawPlantBar(
    plant: Plant,
    yearStart: LocalDate,
    weekPx: Float,
    barTop: Float,
    barHeight: Float,
) {
    val startDate = plant.plantedDate?.let {
        try { LocalDate.parse(it) } catch (e: Exception) { null }
    } ?: return

    val endDate = plant.expectedHarvest?.let {
        try { LocalDate.parse(it) } catch (e: Exception) { null }
    } ?: plant.daysToHarvest?.let { startDate.plusDays(it.toLong()) }
    ?: startDate.plusDays(60)

    val startWeek = ChronoUnit.WEEKS.between(yearStart, startDate).toFloat().coerceIn(-1f, 52f)
    val endWeek = ChronoUnit.WEEKS.between(yearStart, endDate).toFloat().coerceIn(0f, 53f)

    if (endWeek <= startWeek) return

    val color = statusColor(plant.status)
    drawRect(
        color = color,
        topLeft = Offset(startWeek * weekPx, barTop),
        size = Size((endWeek - startWeek) * weekPx, barHeight),
    )

    // Germination sub-bar
    plant.daysToGermination?.let { days ->
        val germEndWeek = (startWeek + days / 7f).coerceAtMost(endWeek)
        drawRect(
            color = color.copy(alpha = 0.4f),
            topLeft = Offset(startWeek * weekPx, barTop),
            size = Size((germEndWeek - startWeek) * weekPx, barHeight),
        )
    }
}

private fun statusColor(status: String?): Color = when (status?.lowercase()) {
    "growing", "active", "transplanted" -> Color(0xFF4CAF50)
    "harvested" -> Color(0xFF8BC34A)
    "dormant" -> Color(0xFF9E9E9E)
    "planning", "seeded" -> Color(0xFF2196F3)
    "germinated", "seedling" -> Color(0xFF03A9F4)
    else -> Color(0xFF9C27B0)
}
