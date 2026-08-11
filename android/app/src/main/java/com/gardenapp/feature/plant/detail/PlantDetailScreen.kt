package com.gardenapp.feature.plant.detail

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.ui.components.CacheStatusLine
import com.gardenapp.core.ui.components.SkeletonList
import com.gardenapp.feature.plant.detail.tabs.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlantDetailScreen(
    onBack: () -> Unit,
    onEdit: (Int) -> Unit,
    viewModel: PlantDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }
    LaunchedEffect(uiState.message) {
        uiState.message?.let { snackbarHostState.showSnackbar(it); viewModel.dismissMessage() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.plant?.name ?: "Plant", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
                actions = {
                    uiState.plant?.let { plant ->
                        IconButton(onClick = { onEdit(plant.id) }) { Icon(Icons.Default.Edit, "Edit") }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                // Only when there is nothing cached — a background refresh must not
                // hide content that is already on screen.
                uiState.isLoading && uiState.plant == null -> SkeletonList(count = 3)
                uiState.plant != null -> {
                    val plant = uiState.plant!!
                    val tabs = listOf("My Plant", "Overview", "Calendar", "How to Grow", "Companions", "Soil", "Nutrition", "FAQs")
                    var selectedTab by remember { mutableIntStateOf(0) }

                    Column {
                        ScrollableTabRow(selectedTabIndex = selectedTab) {
                            tabs.forEachIndexed { i, label ->
                                Tab(
                                    selected = selectedTab == i,
                                    onClick = { selectedTab = i },
                                    text = { Text(label) },
                                )
                            }
                        }
                        if (uiState.isLoading) {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                        }
                        CacheStatusLine(
                            fetchedAt = uiState.fetchedAt,
                            isRefreshing = uiState.isLoading,
                            refreshFailed = uiState.refreshFailed,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                        )
                        when (selectedTab) {
                            0 -> MyPlantTab(
                                plant = plant,
                                isSavingStatus = uiState.isSavingStatus,
                                onSetStatus = viewModel::setStatus,
                            )
                            1 -> OverviewTab(plant = plant)
                            2 -> CalendarTab(plant = plant)
                            3 -> HowToGrowTab(plant = plant)
                            4 -> CompanionsTab(plant = plant)
                            5 -> SoilTab(plant = plant)
                            6 -> NutritionTab(plant = plant)
                            7 -> FaqsTab(plant = plant)
                        }
                    }
                }
                else -> Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("Plant not found")
                    Button(onClick = { viewModel.load(force = true) }) { Text("Retry") }
                }
            }
        }
    }
}
