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
import androidx.hilt.navigation.compose.hiltViewModel
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
                uiState.isLoading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
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
                    Button(onClick = { viewModel.load() }) { Text("Retry") }
                }
            }
        }
    }
}
