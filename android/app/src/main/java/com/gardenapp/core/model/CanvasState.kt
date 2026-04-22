package com.gardenapp.core.model

data class ViewTransform(
    val scale: Float = 1f,
    val translateX: Float = 0f,
    val translateY: Float = 0f,
) {
    fun clampedScale(newScale: Float) = copy(scale = newScale.coerceIn(0.3f, 2f))
}

data class CanvasSnapshot(
    val beds: List<Bed>,
    val canvasPlants: List<CanvasPlant>,
)
