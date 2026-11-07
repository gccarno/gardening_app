package com.gardenapp.feature.identify

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class PlantIdPreprocessTest {

    @Test
    fun centerSquare_landscape() {
        assertEquals(PlantIdPreprocess.Square(50, 0, 300), PlantIdPreprocess.centerSquare(400, 300))
    }

    @Test
    fun centerSquare_portraitFloorsOddMargin() {
        // Matches Python's (height - side) // 2 and the web's Math.floor.
        assertEquals(PlantIdPreprocess.Square(0, 50, 300), PlantIdPreprocess.centerSquare(300, 401))
    }

    @Test
    fun inSampleSize_keepsShortSideAtLeastTwiceTarget() {
        // 3024 / 4 = 756 >= 448, 3024 / 8 = 378 < 448 -> 4
        assertEquals(4, PlantIdPreprocess.inSampleSize(4032, 3024, 224))
        assertEquals(1, PlantIdPreprocess.inSampleSize(500, 400, 224))
    }

    @Test
    fun toNchw_splitsArgbIntoPlanarRgb() {
        // 2x2: red, green, blue, white — alpha bits must be ignored.
        val argb = intArrayOf(0xFFFF0000.toInt(), 0x8000FF00.toInt(), 0x000000FF, 0xFFFFFFFF.toInt())
        val out = PlantIdPreprocess.toNchw(argb, 2)
        assertArrayEquals(
            floatArrayOf(
                1f, 0f, 0f, 1f,   // R plane
                0f, 1f, 0f, 1f,   // G plane
                0f, 0f, 1f, 1f,   // B plane
            ),
            out, 0f,
        )
    }
}
