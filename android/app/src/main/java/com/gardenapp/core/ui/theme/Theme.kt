package com.gardenapp.core.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Green80 = Color(0xFFA5D6A7)
private val GreenGrey80 = Color(0xFFB2DFDB)
private val Brown80 = Color(0xFFBCAAA4)

private val Green40 = Color(0xFF2E7D32)
private val GreenGrey40 = Color(0xFF00695C)
private val Brown40 = Color(0xFF6D4C41)

private val LightColors = lightColorScheme(
    primary = Green40,
    secondary = GreenGrey40,
    tertiary = Brown40,
    background = Color(0xFFF9FBF7),
    surface = Color(0xFFFFFFFF),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onBackground = Color(0xFF1A1C18),
    onSurface = Color(0xFF1A1C18),
)

private val DarkColors = darkColorScheme(
    primary = Green80,
    secondary = GreenGrey80,
    tertiary = Brown80,
    background = Color(0xFF1A1C18),
    surface = Color(0xFF2D312A),
    onPrimary = Color(0xFF003909),
    onSecondary = Color(0xFF003731),
    onBackground = Color(0xFFE2E3DC),
    onSurface = Color(0xFFE2E3DC),
)

@Composable
fun GardenAppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, content = content)
}
