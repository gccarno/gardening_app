package com.gardenapp.feature.library.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.gardenapp.core.model.LibraryImage
import com.gardenapp.core.network.ServerConfig

@Composable
fun ImageGalleryPager(
    images: List<LibraryImage>,
    onSetPrimary: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (images.isEmpty()) return

    val pagerState = rememberPagerState { images.size }

    Column(modifier = modifier) {
        HorizontalPager(state = pagerState, modifier = Modifier.fillMaxWidth()) { page ->
            val image = images[page]
            Box(modifier = Modifier.fillMaxWidth().height(240.dp)) {
                AsyncImage(
                    model = "${ServerConfig.baseUrl}/static/plant_images/${image.filename}",
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
                if (!image.isPrimary) {
                    Button(
                        onClick = { onSetPrimary(image.id) },
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .padding(8.dp),
                    ) { Text("Set Primary") }
                } else {
                    Surface(
                        modifier = Modifier.align(Alignment.BottomStart).padding(8.dp),
                        color = MaterialTheme.colorScheme.primaryContainer,
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text("Primary", modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }

        // Page indicator
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
            horizontalArrangement = Arrangement.Center,
        ) {
            repeat(images.size) { i ->
                Box(
                    modifier = Modifier
                        .padding(horizontal = 2.dp)
                        .size(if (i == pagerState.currentPage) 8.dp else 6.dp)
                        .padding(1.dp),
                ) {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        shape = MaterialTheme.shapes.small,
                        color = if (i == pagerState.currentPage)
                            MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f),
                    ) {}
                }
            }
        }
    }
}
