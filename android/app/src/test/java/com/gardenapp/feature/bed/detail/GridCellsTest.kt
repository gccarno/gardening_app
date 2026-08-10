package com.gardenapp.feature.bed.detail

import com.gardenapp.core.model.GridPlant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class GridCellsTest {

    private fun plant(id: Int, x: Int, y: Int, spacing: Float?) =
        GridPlant(id = id, gridX = x, gridY = y, plantId = id, plantName = "P$id", spacingIn = spacing)

    @Test
    fun `a 12in plant covers exactly one cell`() {
        val map = cellToPlantMap(listOf(plant(1, 0, 0, 12f)))
        assertEquals(1, map[Pair(0, 0)]?.id)
        assertNull(map[Pair(1, 0)])
    }

    @Test
    fun `a 24in plant covers a 2x2 block from its origin`() {
        val map = cellToPlantMap(listOf(plant(1, 12, 24, 24f)))
        // origin cell is (1, 2)
        listOf(Pair(1, 2), Pair(2, 2), Pair(1, 3), Pair(2, 3)).forEach {
            assertEquals("cell $it should be covered", 1, map[it]?.id)
        }
        assertNull(map[Pair(0, 2)])
        assertNull(map[Pair(3, 2)])
    }

    @Test
    fun `spacing that is not a whole number of cells rounds up`() {
        assertEquals(2, cellSpan(18f))
        assertEquals(1, cellSpan(6f))
        assertEquals(1, cellSpan(null))
        assertEquals(3, cellSpan(30f))
    }
}
