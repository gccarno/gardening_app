package com.gardenapp

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.ListenableWorker
import androidx.work.WorkerFactory
import androidx.work.WorkerParameters
import androidx.work.testing.TestListenableWorkerBuilder
import com.gardenapp.core.dataStore
import com.gardenapp.core.database.GardenDatabase
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.notifications.GardenNotificationWorker
import com.gardenapp.core.notifications.GardenNotifier
import com.gardenapp.core.notifications.InAppNotifier
import com.gardenapp.core.notifications.evaluators.GrowthEvaluator
import com.gardenapp.core.notifications.evaluators.PlantingSuggestionEvaluator
import com.gardenapp.core.notifications.evaluators.WateringEvaluator
import com.gardenapp.feature.auth.AUTH_TOKEN_KEY
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import retrofit2.Retrofit

/**
 * Smoke test: the worker completes successfully in the signed-out state
 * (no auth token in DataStore) without touching the network.
 */
@RunWith(AndroidJUnit4::class)
class GardenNotificationWorkerTest {

    private val context = ApplicationProvider.getApplicationContext<Context>()
    private lateinit var db: GardenDatabase
    private var savedToken: String? = null

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(context, GardenDatabase::class.java)
            .allowMainThreadQueries().build()
        runBlocking {
            context.dataStore.edit { prefs ->
                savedToken = prefs[AUTH_TOKEN_KEY]
                prefs.remove(AUTH_TOKEN_KEY)
            }
        }
    }

    @After
    fun tearDown() {
        runBlocking {
            context.dataStore.edit { prefs ->
                savedToken?.let { prefs[AUTH_TOKEN_KEY] = it }
            }
        }
        db.close()
    }

    @Test
    fun signedOut_returnsSuccessWithoutWork() {
        // API pointed at a dead port: any accidental network call would fail loudly.
        val api = Retrofit.Builder()
            .baseUrl("http://127.0.0.1:1/api/")
            .build()
            .create(ApiService::class.java)
        val factory = object : WorkerFactory() {
            override fun createWorker(
                appContext: Context,
                workerClassName: String,
                workerParameters: WorkerParameters,
            ): ListenableWorker = GardenNotificationWorker(
                appContext, workerParameters,
                db.notificationSettingsDao(), db.gardenDao(),
                WateringEvaluator(api), GrowthEvaluator(api),
                PlantingSuggestionEvaluator(api),
                GardenNotifier(appContext, InAppNotifier()),
            )
        }
        val worker = TestListenableWorkerBuilder<GardenNotificationWorker>(context)
            .setWorkerFactory(factory)
            .build()

        val result = runBlocking { worker.doWork() }
        assertEquals(ListenableWorker.Result.success(), result)
    }
}
