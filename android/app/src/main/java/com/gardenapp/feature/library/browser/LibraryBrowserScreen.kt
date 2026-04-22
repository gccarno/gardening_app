package com.gardenapp.feature.library.browser

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Compare
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import androidx.paging.compose.itemKey

private val TYPE_FILTERS = listOf("vegetable", "herb", "fruit", "flower", "tree", "shrub")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryBrowserScreen(
    onNavigateToDetail: (Int) -> Unit,
    onNavigateToDiff: (Int, Int) -> Unit,
    viewModel: LibraryBrowserViewModel = hiltViewModel(),
) {
    val query by viewModel.query.collectAsState()
    val typeFilter by viewModel.typeFilter.collectAsState()
    val compareIds by viewModel.compareIds.collectAsState()
    val pagedItems = viewModel.pagedLibrary.collectAsLazyPagingItems()

    var selectedTab by remember { mutableIntStateOf(0) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Plant Library", fontWeight = FontWeight.Bold) },
                actions = {
                    if (compareIds.size == 2) {
                        IconButton(onClick = {
                            val ids = compareIds.toList()
                            onNavigateToDiff(ids[0], ids[1])
                            viewModel.clearCompare()
                        }) {
                            Icon(Icons.Default.Compare, "Compare")
                        }
                    }
                },
            )
        },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            TabRow(selectedTabIndex = selectedTab) {
                Tab(selected = selectedTab == 0, onClick = { selectedTab = 0 }, text = { Text("Library") })
                Tab(selected = selectedTab == 1, onClick = { selectedTab = 1 }, text = { Text("Perenual") })
            }

            when (selectedTab) {
                0 -> LibraryTab(
                    query = query,
                    typeFilter = typeFilter,
                    compareIds = compareIds,
                    pagedItems = pagedItems,
                    onQueryChange = viewModel::onQueryChange,
                    onTypeFilterChange = viewModel::onTypeFilterChange,
                    onItemClick = onNavigateToDetail,
                    onToggleCompare = viewModel::toggleCompare,
                )
                1 -> PerenualTab(viewModel = viewModel)
            }
        }
    }
}

@Composable
private fun LibraryTab(
    query: String,
    typeFilter: String?,
    compareIds: Set<Int>,
    pagedItems: androidx.paging.compose.LazyPagingItems<com.gardenapp.core.model.LibraryListEntry>,
    onQueryChange: (String) -> Unit,
    onTypeFilterChange: (String?) -> Unit,
    onItemClick: (Int) -> Unit,
    onToggleCompare: (Int) -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            placeholder = { Text("Search 8,988 plants…") },
            leadingIcon = { Icon(Icons.Default.Search, null) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        )

        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(horizontal = 12.dp),
            modifier = Modifier.padding(bottom = 8.dp),
        ) {
            items(TYPE_FILTERS) { type ->
                FilterChip(
                    selected = typeFilter == type,
                    onClick = { onTypeFilterChange(type) },
                    label = { Text(type.replaceFirstChar(Char::uppercase)) },
                )
            }
        }

        if (compareIds.isNotEmpty()) {
            Surface(
                color = MaterialTheme.colorScheme.secondaryContainer,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    "Compare mode: ${compareIds.size}/2 selected${if (compareIds.size == 2) " — tap Compare ↗" else ""}",
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }

        Box(modifier = Modifier.fillMaxSize()) {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(pagedItems.itemCount, key = pagedItems.itemKey { it.id }) { index ->
                    val entry = pagedItems[index] ?: return@items
                    val isSelected = entry.id in compareIds
                    LibraryRow(
                        entry = entry,
                        isCompareSelected = isSelected,
                        showCompareToggle = compareIds.isNotEmpty() || true,
                        onClick = { onItemClick(entry.id) },
                        onToggleCompare = { onToggleCompare(entry.id) },
                    )
                    HorizontalDivider()
                }

                when (val state = pagedItems.loadState.append) {
                    is LoadState.Loading -> item {
                        Box(modifier = Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                    }
                    is LoadState.Error -> item {
                        Text(
                            "Error loading: ${state.error.message}",
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(16.dp),
                        )
                    }
                    else -> {}
                }
            }

            if (pagedItems.loadState.refresh is LoadState.Loading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }
        }
    }
}

@Composable
private fun LibraryRow(
    entry: com.gardenapp.core.model.LibraryListEntry,
    isCompareSelected: Boolean,
    showCompareToggle: Boolean,
    onClick: () -> Unit,
    onToggleCompare: () -> Unit,
) {
    ListItem(
        headlineContent = { Text(entry.name, fontWeight = FontWeight.Medium) },
        supportingContent = {
            val parts = listOfNotNull(
                entry.type?.replaceFirstChar(Char::uppercase),
                entry.spacingIn?.let { "${it.toInt()}in spacing" },
                entry.daysToHarvest?.let { "${it}d to harvest" },
            )
            if (parts.isNotEmpty()) Text(parts.joinToString(" · "))
        },
        trailingContent = {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                entry.difficulty?.let {
                    Badge(containerColor = difficultyColor(it)) { Text(it) }
                }
                Checkbox(checked = isCompareSelected, onCheckedChange = { onToggleCompare() })
            }
        },
        modifier = Modifier.clickable(onClick = onClick),
    )
}

@Composable
private fun PerenualTab(viewModel: LibraryBrowserViewModel) {
    val perenualQuery by viewModel.perenualQuery.collectAsState()
    val results by viewModel.perenualResults.collectAsState()
    val isLoading by viewModel.perenualLoading.collectAsState()
    val error by viewModel.perenualError.collectAsState()

    Column(modifier = Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = perenualQuery,
                onValueChange = viewModel::onPerenualQueryChange,
                placeholder = { Text("Search Perenual database…") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Button(onClick = viewModel::searchPerenual, enabled = !isLoading) { Text("Search") }
        }

        when {
            isLoading -> Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            error != null -> Text(error!!, color = MaterialTheme.colorScheme.error)
            results.isEmpty() && perenualQuery.isNotBlank() -> Text(
                "No results",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            else -> LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(results) { result ->
                    ListItem(
                        headlineContent = { Text(result.name, fontWeight = FontWeight.Medium) },
                        supportingContent = result.scientificName?.let { { Text(it) } },
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun difficultyColor(difficulty: String) = when (difficulty.lowercase()) {
    "easy" -> MaterialTheme.colorScheme.primaryContainer
    "medium" -> MaterialTheme.colorScheme.secondaryContainer
    "hard" -> MaterialTheme.colorScheme.errorContainer
    else -> MaterialTheme.colorScheme.surfaceVariant
}
