package com.gardenapp.feature.identify

/**
 * Pure parts of the on-device plant-ID preprocessing contract, shared with
 * ml/features/plantid_preprocess.py and apps/web/src/utils/plantid.ts:
 * centred square crop -> resize to input size -> RGB / 255 -> NCHW float32.
 * No Android types here, so plain JVM unit tests cover it.
 */
object PlantIdPreprocess {

    data class Square(val left: Int, val top: Int, val side: Int)

    /** Centred square crop of a width x height image (matches center_square in Python). */
    fun centerSquare(width: Int, height: Int): Square {
        val side = minOf(width, height)
        return Square((width - side) / 2, (height - side) / 2, side)
    }

    /** Largest power-of-two decode subsample that keeps the short side >= 2 x target. */
    fun inSampleSize(width: Int, height: Int, target: Int): Int {
        var sample = 1
        while (minOf(width, height) / (sample * 2) >= target * 2) sample *= 2
        return sample
    }

    /** ARGB pixels (Bitmap.getPixels order) -> planar RGB float32 in [0, 1]. */
    fun toNchw(argb: IntArray, size: Int): FloatArray {
        val plane = size * size
        val out = FloatArray(3 * plane)
        for (i in 0 until plane) {
            val p = argb[i]
            out[i] = ((p shr 16) and 0xFF) / 255f
            out[plane + i] = ((p shr 8) and 0xFF) / 255f
            out[2 * plane + i] = (p and 0xFF) / 255f
        }
        return out
    }
}
