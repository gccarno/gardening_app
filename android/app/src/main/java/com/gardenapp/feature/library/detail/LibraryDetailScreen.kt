package com.gardenapp.feature.library.detail

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.feature.library.detail.components.AddToGardenSheet
import com.gardenapp.feature.library.detail.components.ImageGalleryPager
import com.gardenapp.feature.library.detail.tabs.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryDetailScreen(
    onBack: () -> Unit,
    onNavigateToPlant: (Int) -> Unit,
    viewModel: LibraryDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }
    LaunchedEffect(uiState.message) {
        uiState.message?.let { snackbarHostState.showSnackbar(it); viewModel.dismissMessage() }
    }

    if (uiState.showAddToGarden) {
        AddToGardenSheet(
            gardens = uiState.gardens,
            defaultName = uiState.entry?.name ?: "",
            isSaving = uiState.isSavingPlant,
            onAdd = { gardenId, name, date ->
                viewModel.addToGarden(gardenId, name, date, onNavigateToPlant)
            },
            onDismiss = viewModel::dismissAddToGarden,
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.entry?.name ?: "Plant", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
                actions = {
                    IconButton(onClick = viewModel::openAddToGarden) {
                        Icon(Icons.Default.Add, "Add to garden")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isLoading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                uiState.entry != null -> {
                    val entry = uiState.entry!!
                    val tabs = listOf("Overview", "Seasons", "How to Grow", "Companions", "Soil", "Nutrition", "FAQs", "Images")
                    var selectedTab by remember { mutableIntStateOf(0) }

                    Column {
                        ScrollableTabRow(selectedTabIndex = selectedTab) {
                            tabs.forEachIndexed { i, label ->
                                Tab(selected = selectedTab == i, onClick = { selectedTab = i },
                                    text = { Text(label) })
                            }
                        }
                        when (selectedTab) {
                            0 -> LibraryOverviewTab(entry)
                            1 -> LibrarySeasonsTab(entry)
                            2 -> LibraryHowToGrowTab(entry)
                            3 -> LibraryCompanionsTab(entry)
                            4 -> LibrarySoilTab(entry)
                            5 -> LibraryNutritionTab(entry)
                            6 -> LibraryFaqsTab(entry)
                            7 -> if (uiState.images.isNotEmpty()) {
                                ImageGalleryPager(
                                    images = uiState.images,
                                    onSetPrimary = viewModel::setPrimaryImage,
                                    modifier = Modifier.fillMaxWidth(),
                                )
                            } else {
                                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                    Text("No images available", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                }
                else -> Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("Could not load entry")
                    Button(onClick = { viewModel.load() }) { Text("Retry") }
                }
            }
        }
    }
}
