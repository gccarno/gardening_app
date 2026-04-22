package com.gardenapp.feature.canvas.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.sp
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.CanvasPlant
import com.gardenapp.core.model.ViewTransform

const val PIXELS_PER_FOOT = 80f

private val BED_COLORS = listOf(
    Color(0xFF4CAF50), Color(0xFF2196F3), Color(0xFFFF9800),
    Color(0xFF9C27B0), Color(0xFFF44336), Color(0xFF009688),
    Color(0xFF795548), Color(0xFFE91E63),
)

@Composable
fun PlannerCanvas(
    placedBeds: List<Bed>,
    canvasPlants: List<CanvasPlant>,
    transform: ViewTransform,
    selectedBedId: Int?,
    selectedPlantId: Int?,
    onTransformChange: (ViewTransform) -> Unit,
    onBedSelected: (Int?) -> Unit,
    onPlantSelected: (Int?) -> Unit,
    onBedMoveLocal: (Int, Offset) -> Unit,
    onBedMoveCommit: (Int) -> Unit,
    onPlantMoveLocal: (Int, Offset) -> Unit,
    onPlantMoveCommit: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val textMeasurer = rememberTextMeasurer()
    val primaryColor = MaterialTheme.colorScheme.primary
    val gridColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f)
    val labelStyle = TextStyle(fontSize = 10.sp, color = Color.White)

    fun screenToWorld(screenPos: Offset) = Offset(
        x = (screenPos.x - transform.translateX) / (transform.scale * PIXELS_PER_FOOT),
        y = (screenPos.y - transform.translateY) / (transform.scale * PIXELS_PER_FOOT),
    )

    fun hitTestBed(worldPos: Offset): Bed? = placedBeds.lastOrNull { bed ->
        val x = bed.posX ?: return@lastOrNull false
        val y = bed.posY ?: return@lastOrNull false
        worldPos.x in x..(x + bed.widthFt) && worldPos.y in y..(y + bed.heightFt)
    }

    fun hitTestPlant(worldPos: Offset): CanvasPlant? = canvasPlants.lastOrNull { p ->
        val dx = worldPos.x - p.posX
        val dy = worldPos.y - p.posY
        (dx * dx + dy * dy) <= p.radiusFt * p.radiusFt
    }

    Box(modifier = modifier
        // Tap → select/deselect
        .pointerInput(placedBeds, canvasPlants, transform, selectedBedId, selectedPlantId) {
            detectTapGestures { screenPos ->
                val wp = screenToWorld(screenPos)
                val hitBed = hitTestBed(wp)
                val hitPlant = hitTestPlant(wp)
                when {
                    hitBed != null -> onBedSelected(if (selectedBedId == hitBed.id) null else hitBed.id)
                    hitPlant != null -> onPlantSelected(if (selectedPlantId == hitPlant.id) null else hitPlant.id)
                    else -> { onBedSelected(null); onPlantSelected(null) }
                }
            }
        }
        // Drag → move selected item or pan
        .pointerInput(selectedBedId, selectedPlantId, transform) {
            detectDragGestures(
                onDragEnd = {
                    selectedBedId?.let { onBedMoveCommit(it) }
                    selectedPlantId?.let { onPlantMoveCommit(it) }
                },
            ) { _, dragAmount ->
                when {
                    selectedBedId != null -> {
                        onBedMoveLocal(selectedBedId, dragAmount / (transform.scale * PIXELS_PER_FOOT))
                    }
                    selectedPlantId != null -> {
                        onPlantMoveLocal(selectedPlantId, dragAmount / (transform.scale * PIXELS_PER_FOOT))
                    }
                    else -> onTransformChange(transform.copy(
                        translateX = transform.translateX + dragAmount.x,
                        translateY = transform.translateY + dragAmount.y,
                    ))
                }
            }
        }
        // Pinch-to-zoom
        .pointerInput(transform) {
            detectTransformGestures { centroid, _, zoom, _ ->
                if (zoom != 1f) {
                    val newScale = (transform.scale * zoom).coerceIn(0.3f, 2f)
                    val ratio = newScale / transform.scale
                    onTransformChange(ViewTransform(
                        scale = newScale,
                        translateX = centroid.x - ratio * (centroid.x - transform.translateX),
                        translateY = centroid.y - ratio * (centroid.y - transform.translateY),
                    ))
                }
            }
        },
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            withTransform({
                translate(transform.translateX, transform.translateY)
                scale(transform.scale, transform.scale, Offset.Zero)
            }) {
                drawGrid(gridColor)
                drawBeds(placedBeds, selectedBedId, primaryColor, textMeasurer, labelStyle)
                drawCanvasPlants(canvasPlants, selectedPlantId, primaryColor, textMeasurer, labelStyle)
            }
        }
    }
}

private fun DrawScope.drawGrid(gridColor: Color) {
    val pxPerFt = PIXELS_PER_FOOT
    val cols = (size.width / pxPerFt).toInt() + 2
    val rows = (size.height / pxPerFt).toInt() + 2
    for (c in 0..cols) drawLine(gridColor, Offset(c * pxPerFt, 0f), Offset(c * pxPerFt, size.height))
    for (r in 0..rows) drawLine(gridColor, Offset(0f, r * pxPerFt), Offset(size.width, r * pxPerFt))
}

private fun DrawScope.drawBeds(
    beds: List<Bed>,
    selectedBedId: Int?,
    primaryColor: Color,
    textMeasurer: TextMeasurer,
    labelStyle: TextStyle,
) {
    val pxPerFt = PIXELS_PER_FOOT
    beds.forEachIndexed { i, bed ->
        val x = (bed.posX ?: 0f) * pxPerFt
        val y = (bed.posY ?: 0f) * pxPerFt
        val w = bed.widthFt * pxPerFt
        val h = bed.heightFt * pxPerFt
        val color = BED_COLORS[i % BED_COLORS.size]
        val isSelected = bed.id == selectedBedId

        drawRect(color.copy(alpha = 0.7f), topLeft = Offset(x, y), size = Size(w, h))

        val strokeColor = if (isSelected) primaryColor else Color.White.copy(alpha = 0.8f)
        val strokeWidth = if (isSelected) 3f else 1.5f
        val pathEffect = if (isSelected)
            PathEffect.dashPathEffect(floatArrayOf(12f, 6f), 0f) else null
        drawRect(strokeColor, topLeft = Offset(x, y), size = Size(w, h),
            style = Stroke(width = strokeWidth, pathEffect = pathEffect))

        // Label
        val label = bed.name
        val measured = textMeasurer.measure(label, labelStyle)
        drawText(
            textMeasurer = textMeasurer,
            text = label,
            topLeft = Offset(x + w / 2 - measured.size.width / 2, y + h / 2 - measured.size.height / 2),
            style = labelStyle,
        )
        // Dimensions sub-label
        val dimLabel = "${bed.widthFt.toInt()}×${bed.heightFt.toInt()}ft"
        val dimMeasured = textMeasurer.measure(dimLabel, labelStyle.copy(fontSize = 8.sp))
        drawText(
            textMeasurer = textMeasurer,
            text = dimLabel,
            topLeft = Offset(x + w / 2 - dimMeasured.size.width / 2, y + h / 2 + measured.size.height / 2),
            style = labelStyle.copy(fontSize = 8.sp),
        )
    }
}

private fun DrawScope.drawCanvasPlants(
    plants: List<CanvasPlant>,
    selectedPlantId: Int?,
    primaryColor: Color,
    textMeasurer: TextMeasurer,
    labelStyle: TextStyle,
) {
    val pxPerFt = PIXELS_PER_FOOT
    plants.forEach { plant ->
        val cx = plant.posX * pxPerFt
        val cy = plant.posY * pxPerFt
        val r = plant.radiusFt * pxPerFt
        val isSelected = plant.id == selectedPlantId

        val color = plant.color?.let { parseHexColor(it) } ?: Color(0xFF66BB6A)
        drawCircle(color.copy(alpha = 0.75f), radius = r, center = Offset(cx, cy))

        val strokeColor = if (isSelected) primaryColor else Color.White.copy(alpha = 0.8f)
        val strokeWidth = if (isSelected) 3f else 1.5f
        drawCircle(strokeColor, radius = r, center = Offset(cx, cy), style = Stroke(width = strokeWidth))

        // Label
        val label = (plant.label ?: plant.name).take(12)
        val measured = textMeasurer.measure(label, labelStyle.copy(fontSize = 8.sp))
        drawText(
            textMeasurer = textMeasurer,
            text = label,
            topLeft = Offset(cx - measured.size.width / 2f, cy - measured.size.height / 2f),
            style = labelStyle.copy(fontSize = 8.sp),
        )
    }
}

private fun parseHexColor(hex: String): Color = try {
    val clean = hex.trimStart('#')
    val long = java.lang.Long.parseLong(clean.padStart(8, 'F'), 16)
    Color(long.toInt())
} catch (e: Exception) {
    Color(0xFF66BB6A)
}
