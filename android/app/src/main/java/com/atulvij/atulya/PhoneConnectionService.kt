package com.atulvij.atulya

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.BatteryManager
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** Explicit user-started background session. Effects remain queued until the app is opened. */
class PhoneConnectionService : Service() {
    companion object {
        private const val CHANNEL = "atulya_connection"
        private const val NOTICE = 2002
        private const val STOP = "com.atulvij.atulya.STOP_CONNECTION"
        @Volatile var appForeground = false
        fun enabled(context: Context) = context.getSharedPreferences("device_agent", Context.MODE_PRIVATE)
            .getBoolean("background_enabled", false)
        fun setEnabled(context: Context, value: Boolean) {
            context.getSharedPreferences("device_agent", Context.MODE_PRIVATE).edit()
                .putBoolean("background_enabled", value).commit()
            if (value) context.startForegroundService(Intent(context, PhoneConnectionService::class.java))
            else context.stopService(Intent(context, PhoneConnectionService::class.java))
        }
    }

    private val io = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var active = false
    private val prefs by lazy { getSharedPreferences("device_agent", Context.MODE_PRIVATE) }
    private val outbox by lazy { ReceiptOutbox(
        { prefs.getString("receipts", "[]") ?: "[]" },
        { prefs.edit().putString("receipts", it).commit() },
    ) }
    private val tick = object : Runnable {
        override fun run() {
            if (!active) return
            val next = this
            io.execute {
                if (!appForeground) checkServer()
                main.post { if (active) main.postDelayed(next, 15_000L) }
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "Atulya phone connection", NotificationManager.IMPORTANCE_LOW)
        )
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP || !enabled(this)) {
            prefs.edit().putBoolean("background_enabled", false).commit()
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(NOTICE, notification("Connecting; only ping and battery run in background."))
        if (!active) { active = true; main.post(tick) }
        return START_NOT_STICKY
    }

    private fun notification(message: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, PhoneConnectionService::class.java).setAction(STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("Atulya phone connection").setContentText(message).setContentIntent(open)
            .setOngoing(true).setOnlyAlertOnce(true).addAction(android.R.drawable.ic_menu_close_clear_cancel, "Disconnect", stop)
            .build()
    }
    private fun update(message: String) {
        if (active) getSystemService(NotificationManager::class.java).notify(NOTICE, notification(message))
    }
    private fun post(path: String, body: JSONObject, token: String): JSONObject {
        val conn = URL(BuildConfig.ATULYA_URL.trimEnd('/') + path).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"; conn.connectTimeout = 10_000; conn.readTimeout = 15_000
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            if (conn.responseCode == 401) {
                main.post { setEnabled(this, false) }
                throw IllegalStateException("Pairing revoked")
            }
            check(conn.responseCode == 200) { "Server unavailable" }
            return JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
        } finally { conn.disconnect() }
    }
    private fun checkServer() {
        try {
            val token = prefs.getString("token", null)
            if (token.isNullOrBlank()) { update("Open and sign in to Atulya to pair this phone."); return }
            if (!outbox.flush { post("/api/agents/result", it, token).optBoolean("ok", false) }) {
                update("Waiting for server to accept an execution receipt."); return
            }
            val data = post("/api/agents/background", JSONObject(), token)
            val jobs = data.optJSONArray("jobs")
            if (jobs != null) for (index in 0 until jobs.length()) {
                val job = jobs.getJSONObject(index)
                val kind = job.optString("kind")
                val result = when (kind) {
                    "ping" -> "Phone background connection is online."
                    "battery_status" -> {
                        val battery = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
                        "Battery ${battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)}%; charging=${battery.isCharging}."
                    }
                    else -> "Refused: this command requires the foreground app."
                }
                outbox.record(JSONObject().put("id", job.getString("id")).put("output", result)
                    .put("success", kind == "ping" || kind == "battery_status"))
            }
            outbox.flush { post("/api/agents/result", it, token).optBoolean("ok", false) }
            val waiting = data.optInt("waiting_for_approval")
            update(if (waiting > 0) "$waiting request(s) waiting. Open Atulya to review and approve."
                   else "Connected for ping and battery. Actions need the open app.")
        } catch (_: Exception) { update("Connection interrupted; retrying. Open Atulya to check pairing.") }
    }
    override fun onDestroy() {
        active = false
        main.removeCallbacks(tick)
        io.shutdown()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
}
