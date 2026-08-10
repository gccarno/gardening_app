package com.gardenapp.feature.bed.detail

import com.gardenapp.core.model.GridPlant
import kotlin.math.ceil

/** Inches per grid cell. The backend stores grid_x/grid_y as inch offsets. */
const val INCHES_PER_CELL = 12

/** How many cells a plant covers on each axis, given its spacing in inches. */
fun cellSpan(spacingIn: Float?): Int =
    ceil((spacingIn ?: INCHES_PER_CELL.toFloat()) / INCHES_PER_CELL).toInt().coerceAtLeast(1)

/**
 * Maps every (col, row) a plant covers to that plant, so a plant wider than one
 * cell is hit-testable across its whole footprint — not just its origin cell.
 */
fun cellToPlantMap(placed: List<GridPlant>): Map<Pair<Int, Int>, GridPlant> = buildMap {
    placed.forEach { gp ->
        val col = gp.gridX / INCHES_PER_CELL
        val row = gp.gridY / INCHES_PER_CELL
        val span = cellSpan(gp.spacingIn)
        for (dc in 0 until span) for (dr in 0 until span) {
            put(Pair(col + dc, row + dr), gp)
        }
    }
}
