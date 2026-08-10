package com.gardenapp.core.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import retrofit2.Converter
import retrofit2.Retrofit
import java.lang.reflect.ParameterizedType
import java.lang.reflect.Type

/**
 * Serializes `Map<String, Any?>` request bodies to JSON.
 *
 * Most write endpoints in [ApiService] declare their body as
 * `Map<String, @JvmSuppressWildcards Any?>`. kotlinx-serialization cannot build a
 * serializer for `Any`, so without this factory every one of those calls fails at
 * invocation with:
 *
 *     IllegalArgumentException: Unable to create @Body converter for
 *     java.util.Map<java.lang.String, java.lang.Object>
 *
 * Register this *before* the kotlinx factory; it claims only Map bodies and defers
 * everything else (returns null) so typed @Serializable bodies still go to kotlinx.
 */
class MapBodyConverterFactory : Converter.Factory() {

    override fun requestBodyConverter(
        type: Type,
        parameterAnnotations: Array<out Annotation>,
        methodAnnotations: Array<out Annotation>,
        retrofit: Retrofit,
    ): Converter<*, RequestBody>? {
        val raw = getRawType(type)
        if (!Map::class.java.isAssignableFrom(raw)) return null
        // Only claim String-keyed maps; anything else is not a JSON object.
        val keyType = (type as? ParameterizedType)?.actualTypeArguments?.firstOrNull()
        if (keyType != null && getRawType(keyType) != String::class.java) return null

        return Converter<Map<*, *>, RequestBody> { map ->
            toJsonObject(map).toString().toRequestBody(JSON)
        }
    }

    private fun toJsonObject(map: Map<*, *>): JSONObject {
        val obj = JSONObject()
        map.forEach { (k, v) -> obj.put(k.toString(), wrap(v)) }
        return obj
    }

    /**
     * `JSONObject.NULL` rather than a dropped key: the care endpoints treat an
     * explicit null as "clear this field" and an absent key as "leave it alone".
     */
    private fun wrap(value: Any?): Any = when (value) {
        null -> JSONObject.NULL
        is Map<*, *> -> toJsonObject(value)
        is Collection<*> -> JSONArray().also { arr -> value.forEach { arr.put(wrap(it)) } }
        is Array<*> -> JSONArray().also { arr -> value.forEach { arr.put(wrap(it)) } }
        else -> value
    }

    private companion object {
        val JSON = "application/json; charset=utf-8".toMediaType()
    }
}
