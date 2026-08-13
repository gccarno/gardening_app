package com.gardenapp.core.di

import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.AuthInterceptor
import com.gardenapp.core.network.DynamicBaseUrlInterceptor
import com.gardenapp.core.network.MapBodyConverterFactory
import com.gardenapp.core.network.ServerConfig
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        // Render's free tier spins down after 15 min idle and takes 30-60s to wake,
        // so 30s made the first request after any idle period fail against a healthy
        // server. Read timeouts only fire once something is already answering; a
        // genuinely dead server still fails fast on the connect timeout above.
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(DynamicBaseUrlInterceptor())
        .addInterceptor(AuthInterceptor())
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
            redactHeader("Authorization")
        })
        .build()

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient, json: Json): Retrofit = Retrofit.Builder()
        // Placeholder base URL — DynamicBaseUrlInterceptor rewrites it per-request
        .baseUrl(ServerConfig.apiBaseUrl)
        .client(client)
        // Must precede the kotlinx factory: it handles the Map<String, Any?> bodies
        // kotlinx cannot serialize, and defers every other type back to kotlinx.
        .addConverterFactory(MapBodyConverterFactory())
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): ApiService =
        retrofit.create(ApiService::class.java)
}
