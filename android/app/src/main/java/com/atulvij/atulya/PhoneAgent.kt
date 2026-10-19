package com.atulvij.atulya

import android.Manifest
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.webkit.CookieManager
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.ArrayDeque
import java.util.concurrent.Executors

/**
 * Makes this phone a paired Atulya device, so the assistant knows it can reach it and can ask it to act.
 *
 * - Pairs itself once with the signed-in session; the device token stays in this app's private storage.
 * - While Atulya is open and unlocked it asks the server for jobs every few seconds (the server shows it
 *   online/offline from that), and reports every result back.
 * - Anything with an effect (SMS, call, opening apps/links, media, speech, messages) waits for ALLOW on
 *   the phone. Only ping and battery level, which change nothing, run without asking.
 * - If the owner removes the phone in Devices, it stops and pairs again only after a new sign-in.
 */
class PhoneAgent(
    private val activity: AppCompatActivity,
    private val origin: Uri,
    private val sendSms: (String, String) -> Boolean,
    private val call: (String) -> Boolean,
    private val media: (String) -> Boolean,
) {
    companion object {
        val ABILITIES = listOf("ping", "battery_status", "open_url", "open_app", "send_sms", "place_call",
                               "media_control", "display_message", "say")
        private val NO_APPROVAL = setOf("ping", "battery_status") // read-only; change nothing on the phone
        private const val POLL_MS = 5_000L
    }

    private data class Result(val ok: Boolean, val output: String)

    private val prefs = activity.getSharedPreferences("device_agent", Context.MODE_PRIVATE)
    private val io = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private val waiting = ArrayDeque<JSONObject>()
    private var asking = false
    @Volatile private var running = false
    private var polling = false // main-thread owned: at most one network batch at a time
    private val outbox = ReceiptOutbox(
        { prefs.getString("receipts", "[]") ?: "[]" },
        { prefs.edit().putString("receipts", it).commit() },
    )
    private var tts: TextToSpeech? = null
    private val base get() = origin.toString().trimEnd('/')
    private val tick = object : Runnable {
        override fun run() {
            if (!running || polling) return
            polling = true
            val nextTick = this
            io.execute {
                try { pollOnce() } finally {
                    main.post {
                        polling = false
                        if (running) main.postDelayed(nextTick, POLL_MS)
                    }
                }
            }
        }
    }

    fun start() {
        if (running || io.isShutdown) return
        running = true
        PhoneConnectionService.appForeground = true
        if (PhoneConnectionService.enabled(activity)) {
            try { PhoneConnectionService.setEnabled(activity, true) } catch (_: Exception) { }
        }
        main.post(tick)
        askNext()
    }

    fun stop() {
        running = false
        PhoneConnectionService.appForeground = false
        main.removeCallbacks(tick)
    }

    fun destroy() {
        stop()
        tts?.shutdown()
        io.shutdown()
    }

    private fun http(method: String, path: String, body: JSONObject, headers: Map<String, String>): Pair<Int, String> {
        val conn = URL(base + path).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = method
            conn.connectTimeout = 10_000
            conn.readTimeout = 15_000
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("Content-Type", "application/json")
            headers.forEach { (key, value) -> conn.setRequestProperty(key, value) }
            conn.doOutput = true
            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val text = (if (code < 400) conn.inputStream else conn.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            return code to text
        } finally {
            conn.disconnect()
        }
    }

    private fun sessionCookie(): String? {
        val cookies = CookieManager.getInstance().getCookie(base) ?: return null
        return if (cookies.split(";").any { it.trim().startsWith("atulya_session=") }) cookies else null
    }

    private fun fingerprint(text: String) =
        MessageDigest.getInstance("SHA-256").digest(text.toByteArray()).joinToString("") { "%02x".format(it) }

    private fun newName(): String {
        val model = Build.MODEL.replace(Regex("[^A-Za-z0-9 _-]"), "").trim().take(22).ifBlank { "Android" }
        val suffix = ByteArray(2).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }
        return "Phone $model $suffix".take(40)
    }

    /** Pair once with the signed-in session. Returns the device token, or null while signed out. */
    private fun ensurePaired(): String? {
        prefs.getString("token", null)?.let { return it }
        val cookies = sessionCookie() ?: return null
        // Removed by the owner: wait for a new sign-in before pairing again.
        if (prefs.getString("removed_session", null) == fingerprint(cookies)) return null
        val name = prefs.getString("name", null) ?: newName().also { prefs.edit().putString("name", it).apply() }
        val body = JSONObject().put("name", name).put("abilities", JSONArray(ABILITIES)).put("device_type", "android")
        val (code, text) = http("POST", "/api/devices/pair", body, mapOf("Cookie" to cookies))
        if (code == 422 && text.contains("already paired")) {
            prefs.edit().putString("name", newName()).apply() // this install lost its token: use a fresh name
            return null
        }
        if (code != 201) return null
        val token = JSONObject(text).optString("token")
        if (token.isBlank()) return null
        prefs.edit().putString("token", token).remove("removed_session").apply()
        return token
    }

    private fun bearer(token: String) = mapOf("Authorization" to "Bearer $token")

    private fun pollOnce() {
        try {
            if (!running) return
            val token = ensurePaired() ?: return
            if (!flushReceipts(token) || !running) return
            val (code, text) = http("POST", "/api/agents/poll", JSONObject(), bearer(token))
            if (code == 401) {
                revoked()
                return
            }
            if (code != 200) return
            val jobs = JSONObject(text).optJSONArray("jobs") ?: return
            for (index in 0 until jobs.length()) {
                val job = jobs.getJSONObject(index)
                main.post { handle(job) }
            }
        } catch (_: Exception) {
            // Offline or server restarting: try again on the next tick.
        }
    }

    private fun handle(job: JSONObject) {
        if (io.isShutdown) return
        if (!running || activity.isFinishing || activity.isDestroyed) {
            io.execute { report(job, Result(false, "Phone app left the foreground; action was not executed.")) }
            return
        }
        if (job.optString("kind") in NO_APPROVAL) {
            val result = run(job)
            io.execute { report(job, result) }
            return
        }
        waiting.add(job)
        askNext()
    }

    private fun askNext() {
        if (!running || asking || activity.isFinishing || activity.isDestroyed) return
        val job = waiting.poll() ?: return
        asking = true
        AlertDialog.Builder(activity)
            .setTitle("Atulya wants to use this phone")
            .setMessage(describe(job))
            .setCancelable(false)
            .setPositiveButton("ALLOW") { _, _ ->
                val result = run(job)
                io.execute { report(job, result) }
                asking = false
                askNext()
            }
            .setNegativeButton("DENY") { _, _ ->
                io.execute { report(job, Result(false, "Denied on the phone.")) }
                asking = false
                askNext()
            }
            .show()
    }

    private fun describe(job: JSONObject): String {
        val detail = job.optString("detail").trim()
        return when (job.optString("kind")) {
            "open_url" -> "Open this link:\n$detail"
            "open_app" -> "Open the app \"$detail\"."
            "send_sms" -> smsParts(detail)?.let { (to, body) -> "Send an SMS to $to:\n\"$body\"" } ?: "Send an SMS ($detail)."
            "place_call" -> "Call $detail."
            "media_control" -> "Media: $detail."
            "display_message" -> "Show this message:\n\"$detail\""
            "say" -> "Say aloud:\n\"$detail\""
            else -> "${job.optString("kind")}: $detail"
        }
    }

    private fun granted(permission: String) =
        ContextCompat.checkSelfPermission(activity, permission) == PackageManager.PERMISSION_GRANTED

    /** {"to": "+91…", "body": "…"} or "+91…: text". */
    private fun smsParts(detail: String): Pair<String, String>? {
        try {
            val json = JSONObject(detail)
            val to = json.optString("to").trim()
            val body = json.optString("body").trim()
            if (to.isNotEmpty() && body.isNotEmpty()) return to to body
        } catch (_: Exception) {
        }
        val split = detail.indexOf(':')
        if (split <= 0) return null
        val to = detail.substring(0, split).trim()
        val body = detail.substring(split + 1).trim()
        return if (to.isNotEmpty() && body.isNotEmpty()) to to body else null
    }

    private fun run(job: JSONObject): Result {
        val detail = job.optString("detail").trim()
        return try {
            when (val kind = job.optString("kind")) {
                "ping" -> Result(true, "${prefs.getString("name", "This phone")} is online.")
                "battery_status" -> {
                    val battery = activity.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
                    val level = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                    Result(true, "Battery $level%${if (battery.isCharging) ", charging" else ""}.")
                }
                "open_url" -> {
                    val uri = Uri.parse(detail)
                    if (uri.scheme != "https" || uri.host.isNullOrBlank()) Result(false, "Only https links can be opened.")
                    else {
                        activity.startActivity(Intent(Intent.ACTION_VIEW, uri))
                        Result(true, "Opened $detail on the phone.")
                    }
                }
                "open_app" -> openApp(detail)
                "send_sms" -> {
                    val (to, body) = smsParts(detail) ?: return Result(false, "Give the SMS as {\"to\": \"+91…\", \"body\": \"…\"}.")
                    val direct = granted(Manifest.permission.SEND_SMS)
                    if (!sendSms(to, body)) Result(false, "Could not prepare the SMS to $to.")
                    else Result(true, if (direct) "SMS handed to Android for sending to $to."
                                      else "SMS app opened with the message to $to; it is sent only when you tap send.")
                }
                "place_call" -> {
                    val direct = granted(Manifest.permission.CALL_PHONE)
                    if (!call(detail)) Result(false, "Could not call $detail.")
                    else Result(true, if (direct) "Calling $detail." else "Dialer opened with $detail; the call starts when you tap call.")
                }
                "media_control" -> if (media(detail.lowercase())) Result(true, "Requested media control: $detail; audible playback is not confirmed.")
                                   else Result(false, "No prepared Atulya audio stream, or unsupported control. Start an audio stream first; controls support play, pause and stop.")
                "display_message" -> {
                    Toast.makeText(activity, detail.take(300), Toast.LENGTH_LONG).show()
                    Result(true, "Message shown on the phone.")
                }
                "say" -> say(detail)
                else -> Result(false, "This phone does not support $kind.")
            }
        } catch (error: Exception) {
            Result(false, "Failed on the phone: ${error.javaClass.simpleName}.")
        }
    }

    private fun openApp(name: String): Result {
        if (name.isBlank()) return Result(false, "Which app?")
        val manager = activity.packageManager
        val apps = manager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
        val match = apps.firstOrNull { it.loadLabel(manager).toString().equals(name, ignoreCase = true) }
            ?: apps.firstOrNull { it.loadLabel(manager).toString().contains(name, ignoreCase = true) }
            ?: return Result(false, "No app called \"$name\" on this phone.")
        val launch = manager.getLaunchIntentForPackage(match.activityInfo.packageName)
            ?: return Result(false, "\"$name\" cannot be opened.")
        activity.startActivity(launch)
        return Result(true, "Opened ${match.loadLabel(manager)}.")
    }

    private fun say(text: String): Result {
        if (text.isBlank()) return Result(false, "Nothing to say.")
        val line = text.take(500)
        val engine = tts
        if (engine == null) {
            tts = TextToSpeech(activity) { status ->
                if (status == TextToSpeech.SUCCESS) tts?.speak(line, TextToSpeech.QUEUE_ADD, null, "atulya")
            }
        } else {
            engine.speak(line, TextToSpeech.QUEUE_ADD, null, "atulya")
        }
        return Result(true, "Handed to the phone's voice to say aloud.")
    }

    private fun report(job: JSONObject, result: Result) {
        try {
            outbox.record(JSONObject().put("id", job.getString("id"))
                .put("output", result.output.take(3900)).put("success", result.ok))
            val token = prefs.getString("token", null) ?: return
            flushReceipts(token)
        } catch (_: Exception) {
            // The persisted receipt is retried before the next poll, without repeating the action.
        }
    }

    private fun flushReceipts(token: String): Boolean = outbox.flush { receipt ->
        val (code, text) = http("POST", "/api/agents/result", receipt, bearer(token))
        if (code == 401) revoked()
        code == 200 && JSONObject(text).optBoolean("ok", false)
    }

    private fun revoked() {
        val cookies = sessionCookie()
        // Receipts belong to the revoked device; never submit them under a new pairing.
        prefs.edit().remove("token").remove("receipts")
            .putString("removed_session", cookies?.let(::fingerprint) ?: "signed-out").commit()
    }
}
