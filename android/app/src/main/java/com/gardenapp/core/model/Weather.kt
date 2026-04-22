package com.gardenapp.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class WeatherData(
    val current: CurrentWeather? = null,
    val daily: List<DailyForecast> = emptyList(),
    val frost: FrostInfo? = null,
)

@Serializable
data class CurrentWeather(
    val temp: Double? = null,
    val humidity: Double? = null,
    val precipitation: Double? = null,
    @SerialName("wind_speed") val windSpeed: Double? = null,
    val condition: String? = null,
)

@Serializable
data class DailyForecast(
    val date: String,
    val high: Double? = null,
    val low: Double? = null,
    @SerialName("precip_prob") val precipProb: Double? = null,
    val uv: Double? = null,
    val condition: String? = null,
)

@Serializable
data class FrostInfo(
    @SerialName("last_spring") val lastSpring: String? = null,
    @SerialName("first_fall") val firstFall: String? = null,
    @SerialName("frost_free") val frostFree: Int? = null,
    @SerialName("station_name") val stationName: String? = null,
    @SerialName("station_distance_km") val stationDistanceKm: Double? = null,
)
