package com.gardenapp.core.model

import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class AuthUser(
    val id: Int,
    val email: String,
    val display_name: String? = null,
)

@Serializable
data class LoginResponse(
    val token: String,
    val user: AuthUser,
)
