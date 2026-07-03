package com.gardenapp.core.network

import android.util.Log
import retrofit2.HttpException

sealed class NetworkResult<out T> {
    data class Success<T>(val data: T) : NetworkResult<T>()
    data class Error(val message: String, val code: Int? = null) : NetworkResult<Nothing>()
    data object Loading : NetworkResult<Nothing>()
}

/** Map an exception to a NetworkResult.Error, preserving the HTTP status code. */
fun Exception.toNetworkError(tag: String = "Network"): NetworkResult.Error {
    Log.e(tag, "request failed", this)
    return when (this) {
        is HttpException -> NetworkResult.Error(
            message = response()?.errorBody()?.string()?.take(200) ?: message(),
            code = code(),
        )
        else -> NetworkResult.Error(message ?: "Network error")
    }
}

inline fun <T> NetworkResult<T>.onSuccess(action: (T) -> Unit): NetworkResult<T> {
    if (this is NetworkResult.Success) action(data)
    return this
}

inline fun <T> NetworkResult<T>.onError(action: (String, Int?) -> Unit): NetworkResult<T> {
    if (this is NetworkResult.Error) action(message, code)
    return this
}
