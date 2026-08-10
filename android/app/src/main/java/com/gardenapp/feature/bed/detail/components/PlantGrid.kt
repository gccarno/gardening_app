package com.gardenapp.feature.bed.detail.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.GridPlant
import com.gardenapp.feature.bed.detail.INCHES_PER_CELL
import com.gardenapp.feature.bed.detail.cellSpan
import com.gardenapp.feature.bed.detail.cellToPlantMap

/** Cell size in dp — 1ft per cell */
private val CELL_SIZE_DP: Dp = 56.dp

/** Test tag for the cell at (col, row) — used by the instrumented bed-grid test. */
fun bedCellTag(col: Int, row: Int) = "bed-cell-$col-$row"

// Plant colours by first letter, deterministic
private val PLANT_COLORS = listOf(
    Color(0xFF4CAF50), Color(0xFF8BC34A), Color(0xFFFF9800), Color(0xFFE91E63),
    Color(0xFF9C27B0), Color(0xFF2196F3), Color(0xFF00BCD4), Color(0xFFFF5722),
)
private fun plantColor(name: String) = PLANT_COLORS[name.hashCode().and(0x7FFFFFFF) % PLANT_COLORS.size]

/**
 * Interactive 1ft-cell grid for a raised bed.
 *
 * Grid positions are in inches: gridX/gridY are inch offsets.
 * At 12in/cell, column = gridX / 12, row = gridY / 12.
 *
 * The grid is drawn on a single canvas (so a plant can span several cells) with a
 * transparent, clickable Box per cell layered on top. The per-cell Boxes are what
 * make taps work: a single `combinedClickable` disambiguates click from long-click,
 * whereas stacked `detectTapGestures` modifiers fight over the same pointer-down.
 *
 * Tap cell        → onCellTap(gridX, gridY)  in inches
 * Long press cell → onCellLongPress(gridX, gridY) in inches
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun PlantGrid(
    widthFt: Int,
    heightFt: Int,
    placed: List<GridPlant>,
    onCellTap: (gridX: Int, gridY: Int) -> Unit,
    onCellLongPress: (gridX: Int, gridY: Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val density = LocalDensity.current
    val cellPx = with(density) { CELL_SIZE_DP.toPx() }
    val cols = widthFt
    val rows = heightFt

    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
    val emptyFill = MaterialTheme.colorScheme.surfaceVariant
    val textColor = MaterialTheme.colorScheme.onSurface

    val cellToPlant = remember(placed) { cellToPlantMap(placed) }

    Box(
        modifier = modifier
            .horizontalScroll(rememberScrollState()),
    ) {
        Box(
            modifier = Modifier
                .size(width = CELL_SIZE_DP * cols, height = CELL_SIZE_DP * rows)
                .drawWithCache {
                    onDrawBehind {
                        drawGrid(cols, rows, cellPx, emptyFill, gridColor, cellToPlant, textColor)
                    }
                },
        ) {
            Column {
                for (row in 0 until rows) {
                    Row {
                        for (col in 0 until cols) {
                            val gp = cellToPlant[Pair(col, row)]
                            Box(
                                modifier = Modifier
                                    .size(CELL_SIZE_DP)
                                    .testTag(bedCellTag(col, row))
                                    .semantics {
                                        contentDescription =
                                            gp?.plantName ?: "Empty cell $col,$row"
                                    }
                                    .combinedClickable(
                                        onClick = {
                                            onCellTap(col * INCHES_PER_CELL, row * INCHES_PER_CELL)
                                        },
                                        onLongClick = {
                                            onCellLongPress(col * INCHES_PER_CELL, row * INCHES_PER_CELL)
                                        },
                                    ),
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun DrawScope.drawGrid(
    cols: Int,
    rows: Int,
    cellPx: Float,
    emptyFill: Color,
    gridColor: Color,
    cellToPlant: Map<Pair<Int, Int>, GridPlant>,
    textColor: Color,
) {
    // Background
    drawRect(emptyFill)

    // Draw occupied plant cells first
    for (col in 0 until cols) {
        for (row in 0 until rows) {
            val gp = cellToPlant[Pair(col, row)] ?: continue
            val color = plantColor(gp.plantName)
            val left = col * cellPx
            val top = row * cellPx

            // Only draw fill + label once for the top-left cell of this plant
            val originCol = gp.gridX / INCHES_PER_CELL
            val originRow = gp.gridY / INCHES_PER_CELL
            if (col == originCol && row == originRow) {
                val span = cellSpan(gp.spacingIn)
                val w = (span * cellPx).coerceAtMost(cols * cellPx - left)
                val h = (span * cellPx).coerceAtMost(rows * cellPx - top)
                drawRect(color = color.copy(alpha = 0.7f), topLeft = Offset(left, top), size = Size(w, h))
                drawRect(color = color, topLeft = Offset(left, top), size = Size(w, h), style = Stroke(width = 2f))

                // Draw initial letter as a simple text proxy using drawCircle
                val cx = left + w / 2
                val cy = top + h / 2
                drawCircle(color = Color.White.copy(alpha = 0.9f), radius = (cellPx * 0.25f).coerceAtMost(14f),
                    center = Offset(cx, cy))
            }
        }
    }

    // Grid lines
    for (c in 0..cols) {
        drawLine(gridColor, Offset(c * cellPx, 0f), Offset(c * cellPx, rows * cellPx), strokeWidth = 1f)
    }
    for (r in 0..rows) {
        drawLine(gridColor, Offset(0f, r * cellPx), Offset(cols * cellPx, r * cellPx), strokeWidth = 1f)
    }
}
