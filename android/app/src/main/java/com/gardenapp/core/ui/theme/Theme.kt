package com.gardenapp.core.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import com.gardenapp.R

// ── Botanical Almanac palette (mirrors apps/web/src/style.css tokens) ────────

// Ink & paper
private val Paper = Color(0xFFF7F4EC)
private val Vellum = Color(0xFFFDFBF5)
private val Ink = Color(0xFF23301F)
private val InkMuted = Color(0xFF77795E)

// Botanical greens
private val Moss = Color(0xFF3D5A34)
private val Fern = Color(0xFFE9EFE2)
private val Leaf = Color(0xFF5F9557)

// Bronze accent & rules
private val Bronze = Color(0xFF9C6B2F)
private val BronzeSoft = Color(0xFFC89454)
private val Rule = Color(0xFFD8D2C0)

private val Madder = Color(0xFFA34730)

// Midnight herbarium (dark)
private val NightPaper = Color(0xFF1B211A)
private val NightVellum = Color(0xFF232B21)
private val NightInk = Color(0xFFE8E6D9)
private val NightInkMuted = Color(0xFF9BA089)
private val NightMoss = Color(0xFF8FB380)
private val NightFern = Color(0xFF2E3A2A)
private val NightLeaf = Color(0xFF6FA863)
private val NightRule = Color(0xFF3A4234)
private val NightMadder = Color(0xFFC96A52)

private val LightColors = lightColorScheme(
    primary = Moss,
    onPrimary = Color.White,
    primaryContainer = Fern,
    onPrimaryContainer = Ink,
    secondary = Bronze,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF2E4CE),
    onSecondaryContainer = Color(0xFF4A3312),
    tertiary = Leaf,
    onTertiary = Color.White,
    background = Paper,
    onBackground = Ink,
    surface = Vellum,
    onSurface = Ink,
    surfaceVariant = Color(0xFFEDE9DC),
    onSurfaceVariant = InkMuted,
    outline = Rule,
    outlineVariant = Rule,
    error = Madder,
    onError = Color.White,
)

private val DarkColors = darkColorScheme(
    primary = NightMoss,
    onPrimary = Color(0xFF1F2A1B),
    primaryContainer = NightFern,
    onPrimaryContainer = NightInk,
    secondary = BronzeSoft,
    onSecondary = Color(0xFF33240D),
    secondaryContainer = Color(0xFF4A3312),
    onSecondaryContainer = Color(0xFFF2E4CE),
    tertiary = NightLeaf,
    onTertiary = Color(0xFF14210F),
    background = NightPaper,
    onBackground = NightInk,
    surface = NightVellum,
    onSurface = NightInk,
    surfaceVariant = Color(0xFF2A3226),
    onSurfaceVariant = NightInkMuted,
    outline = NightRule,
    outlineVariant = NightRule,
    error = NightMadder,
    onError = Color(0xFF2A0F06),
)

// ── Typography: Fraunces for display/headline/title, default sans for body ──

private val Fraunces = FontFamily(
    Font(R.font.fraunces, weight = FontWeight.Normal),
)

private val AlmanacTypography = Typography().let { base ->
    base.copy(
        displayLarge = base.displayLarge.copy(fontFamily = Fraunces),
        displayMedium = base.displayMedium.copy(fontFamily = Fraunces),
        displaySmall = base.displaySmall.copy(fontFamily = Fraunces),
        headlineLarge = base.headlineLarge.copy(fontFamily = Fraunces),
        headlineMedium = base.headlineMedium.copy(fontFamily = Fraunces),
        headlineSmall = base.headlineSmall.copy(fontFamily = Fraunces),
        titleLarge = base.titleLarge.copy(fontFamily = Fraunces),
        titleMedium = base.titleMedium.copy(fontFamily = Fraunces),
    )
}

@Composable
fun GardenAppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colors,
        typography = AlmanacTypography,
        content = content,
    )
}
