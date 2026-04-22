package com.gardenapp.feature.canvas.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Redo
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.ZoomIn
import androidx.compose.material.icons.filled.ZoomOut
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.ViewTransform

@Composable
fun CanvasToolbar(
    title: String,
    transform: ViewTransform,
    canUndo: Boolean,
    canRedo: Boolean,
    showRightPanel: Boolean,
    onBack: () -> Unit,
    onUndo: () -> Unit,
    onRedo: () -> Unit,
    onZoomIn: () -> Unit,
    onZoomOut: () -> Unit,
    onToggleRightPanel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(tonalElevation = 4.dp, modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }

            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f).padding(horizontal = 4.dp),
            )

            Text(
                "×${"%.1f".format(transform.scale)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            IconButton(onClick = onZoomOut) { Icon(Icons.Default.ZoomOut, "Zoom out") }
            IconButton(onClick = onZoomIn) { Icon(Icons.Default.ZoomIn, "Zoom in") }
            IconButton(onClick = onUndo, enabled = canUndo) {
                Icon(Icons.AutoMirrored.Filled.Undo, "Undo")
            }
            IconButton(onClick = onRedo, enabled = canRedo) {
                Icon(Icons.AutoMirrored.Filled.Redo, "Redo")
            }
            IconButton(onClick = onToggleRightPanel) {
                Icon(Icons.Default.Info, "Info panel",
                    tint = if (showRightPanel) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.onSurface)
            }
        }
    }
}
