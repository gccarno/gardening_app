package com.gardenapp.feature.identify

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.util.Log
import com.gardenapp.core.network.ApiService
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.ByteArrayInputStream
import java.io.File
import java.nio.FloatBuffer
import javax.inject.Inject
import javax.inject.Singleton

/**
 * On-device plant identification: runs the ONNX image tower locally and sends
 * only the embedding to POST /api/identify/embedding. Mirrors
 * apps/web/src/utils/plantid.ts; the preprocessing contract lives in
 * PlantIdPreprocess and ml/features/plantid_preprocess.py.
 *
 * The model is downloaded once per version from GET /api/identify/model/{v}.onnx
 * and cached in filesDir — not bundled — so a new version ships without an app
 * release, and a retired one (409) is replaced on the next call.
 */
@Singleton
class PlantIdModel @Inject constructor(
    private val api: ApiService,
    @ApplicationContext private val context: Context,
) {
    private class Loaded(val version: String, val inputSize: Int, val session: OrtSession)

    private val mutex = Mutex()
    private var loaded: Loaded? = null

    private suspend fun load(): Loaded = mutex.withLock {
        loaded?.let { return@withLock it }
        val cfg = api.plantIdModel().jsonObject
        val version = cfg["model_version"]!!.jsonPrimitive.content
        val size = cfg["input_size"]!!.jsonPrimitive.int
        val file = withContext(Dispatchers.IO) { cachedModel(version) }
        val session = OrtEnvironment.getEnvironment()
            .createSession(file.absolutePath, OrtSession.SessionOptions())
        Loaded(version, size, session).also { loaded = it }
    }

    private suspend fun cachedModel(version: String): File {
        val dir = File(context.filesDir, "plantid").apply { mkdirs() }
        val file = File(dir, "plantid_$version.onnx")
        if (!file.exists()) {
            val part = File(dir, "${file.name}.part")
            api.downloadPlantIdModel(version).byteStream().use { input ->
                part.outputStream().use { input.copyTo(it) }
            }
            part.renameTo(file)
            // Drop retired versions — only one model is ever in use.
            dir.listFiles()?.filter { it != file }?.forEach { it.delete() }
        }
        return file
    }

    /**
     * Identify on-device. Returns the server's response (same shape as
     * POST /api/identify, plus `confident`), or null whenever the local path
     * can't answer — the caller then asks Claude.
     */
    suspend fun identify(photo: ByteArray): JsonObject? = try {
        val m = load()
        val embedding = withContext(Dispatchers.Default) { embed(m, preprocess(photo, m.inputSize)) }
        val body = buildJsonObject {
            put("embedding", JsonArray(embedding.map { JsonPrimitive(it) }))
            put("model_version", m.version)
            put("top_k", 3)
        }
        val res = api.identifyEmbedding(body)
        if (res.code() == 409) {
            // Version retired server-side: reload config and model next time.
            mutex.withLock { loaded?.session?.close(); loaded = null }
        }
        if (res.isSuccessful) res.body()?.jsonObject else null
    } catch (e: Exception) {
        Log.w("PlantIdModel", "on-device identify unavailable", e)
        null
    }

    private fun embed(m: Loaded, pixels: FloatArray): FloatArray {
        val env = OrtEnvironment.getEnvironment()
        val shape = longArrayOf(1, 3, m.inputSize.toLong(), m.inputSize.toLong())
        OnnxTensor.createTensor(env, FloatBuffer.wrap(pixels), shape).use { input ->
            m.session.run(mapOf("pixels" to input)).use { out ->
                @Suppress("UNCHECKED_CAST")
                return (out[0].value as Array<FloatArray>)[0]
            }
        }
    }

    companion object {
        /** Photo bytes -> NCHW float32, matching ml/features/plantid_preprocess.py. */
        fun preprocess(photo: ByteArray, size: Int): FloatArray {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(photo, 0, photo.size, bounds)
            val opts = BitmapFactory.Options().apply {
                inSampleSize = PlantIdPreprocess.inSampleSize(bounds.outWidth, bounds.outHeight, size)
            }
            var bmp = BitmapFactory.decodeByteArray(photo, 0, photo.size, opts)
                ?: throw IllegalArgumentException("undecodable image")
            bmp = applyExifRotation(bmp, photo)
            val sq = PlantIdPreprocess.centerSquare(bmp.width, bmp.height)
            var img = Bitmap.createBitmap(bmp, sq.left, sq.top, sq.side, sq.side)
            // Halve while more than 2x too big: a bilinear scale only samples 2x2
            // pixels, so one big jump aliases where PIL's antialiased resize doesn't.
            while (img.width > size * 2) {
                img = Bitmap.createScaledBitmap(img, img.width / 2, img.height / 2, true)
            }
            img = Bitmap.createScaledBitmap(img, size, size, true)
            val argb = IntArray(size * size)
            img.getPixels(argb, 0, size, 0, 0, size, size)
            return PlantIdPreprocess.toNchw(argb, size)
        }

        private fun applyExifRotation(bmp: Bitmap, photo: ByteArray): Bitmap {
            val degrees = when (ExifInterface(ByteArrayInputStream(photo))
                .getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90f
                ExifInterface.ORIENTATION_ROTATE_180 -> 180f
                ExifInterface.ORIENTATION_ROTATE_270 -> 270f
                else -> return bmp
            }
            return Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height,
                                       Matrix().apply { postRotate(degrees) }, true)
        }
    }
}
