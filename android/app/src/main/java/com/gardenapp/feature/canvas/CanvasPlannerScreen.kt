package com.gardenapp.feature.canvas

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.ViewTransform
import com.gardenapp.feature.canvas.components.*

@Composable
fun CanvasPlannerScreen(
    onBack: () -> Unit,
    viewModel: CanvasPlannerViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            // Top toolbar
            CanvasToolbar(
                title = "Garden Planner",
                transform = uiState.transform,
                canUndo = uiState.canUndo,
                canRedo = uiState.canRedo,
                showRightPanel = uiState.showRightPanel,
                onBack = onBack,
                onUndo = viewModel::undo,
                onRedo = viewModel::redo,
                onZoomIn = {
                    val t = uiState.transform
                    viewModel.setTransform(t.clampedScale(t.scale * 1.25f))
                },
                onZoomOut = {
                    val t = uiState.transform
                    viewModel.setTransform(t.clampedScale(t.scale * 0.8f))
                },
                onToggleRightPanel = viewModel::toggleRightPanel,
            )

            // Main content area
            when {
                uiState.isLoading -> Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }

                else -> Row(modifier = Modifier.fillMaxSize()) {
                    // Left sidebar — bed list
                    BedSidebarDrawer(
                        sidebarBeds = uiState.sidebarBeds,
                        placedBedIds = uiState.placedBeds.map { it.id }.toSet(),
                        onAddBed = viewModel::addBedToCanvas,
                    )

                    // Central canvas
                    PlannerCanvas(
                        placedBeds = uiState.placedBeds,
                        canvasPlants = uiState.canvasPlants,
                        transform = uiState.transform,
                        selectedBedId = uiState.selectedBedId,
                        selectedPlantId = uiState.selectedPlantId,
                        onTransformChange = viewModel::setTransform,
                        onBedSelected = viewModel::selectBed,
                        onPlantSelected = viewModel::selectPlant,
                        onBedMoveLocal = viewModel::moveBedLocal,
                        onBedMoveCommit = viewModel::commitBedMove,
                        onPlantMoveLocal = viewModel::movePlantLocal,
                        onPlantMoveCommit = viewModel::commitPlantMove,
                        modifier = Modifier.weight(1f).fillMaxHeight(),
                    )

                    // Right panel (conditional)
                    if (uiState.showRightPanel) {
                        RightInfoPanel(
                            placedBeds = uiState.placedBeds,
                            canvasPlants = uiState.canvasPlants,
                            selectedBedId = uiState.selectedBedId,
                        )
                    }
                }
            }
        }
    }
}
