package com.atulvij.atulya

import android.app.PendingIntent
import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.WindowManager
import android.widget.FrameLayout
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.CookieManager
import android.util.Base64
import android.widget.Toast
import java.security.MessageDigest
import java.security.SecureRandom
import java.net.URLEncoder
import java.util.concurrent.Executors
import androidx.appcompat.app.AppCompatActivity
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebSettingsCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import org.json.JSONObject

/**
 * Atulya for Android.
 *
 * Security: the app is locked with fingerprint/face (or the device PIN) every time it comes
 * to the foreground; screenshots and the recent-apps preview are blocked; only the
 * configured Atulya origin has privileged features; other websites use a separate browser view;
 * the WebView gets microphone/camera only for that origin and only after Android grants them.
 */
class MainActivity : AppCompatActivity() {
    companion object {
        // Lives as long as the app process: reopening within the grace period doesn't ask again,
        // even when Android recreated the screen. A killed process always asks.
        private var lastUnlockAt = 0L
    }

    private lateinit var web: WebView
    private lateinit var content: FrameLayout
    private var browser: InAppBrowser? = null
    private var unlocked = System.currentTimeMillis() - lastUnlockAt < 2 * 60 * 1000L
    private var leftAt = 0L
    private var pendingUrl: String? = null
    private val relockAfterMs = 2 * 60 * 1000L // quick trips (copying a code from Telegram) don't re-lock
    private val origin: Uri = Uri.parse(BuildConfig.ATULYA_URL)
    private var recognizer: SpeechRecognizer? = null
    private var pendingGeo: Pair<String, GeolocationPermissions.Callback>? = null
    private var pendingMedia: PermissionRequest? = null
    private var voiceReply: JavaScriptReplyProxy? = null
    private val cookieWriter = Executors.newSingleThreadExecutor()
    private lateinit var phone: PhoneAgent

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Screens stay private (no screenshots/recents preview); only the CI emulator test build allows capture.
        if (!BuildConfig.ALLOW_SCREENSHOTS) {
            window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        }
        web = WebView(this)
        content = FrameLayout(this)
        content.addView(web, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        setContentView(content)
        configureWebView()
        phone = PhoneAgent(this, origin, ::sendDirectSms, ::callDirect) { command ->
            when (command) {
                "play", "resume" -> controlMediaStream(MediaPlaybackService.ACTION_PLAY)
                "pause" -> controlMediaStream(MediaPlaybackService.ACTION_PAUSE)
                "stop" -> controlMediaStream(MediaPlaybackService.ACTION_STOP)
                else -> false
            }
        }
        if (savedInstanceState != null) web.restoreState(savedInstanceState)
        pendingUrl = linkFrom(intent)
    }

    override fun onPause() {
        // Battery: in the background the page, its timers, the 3D scene and any location request all stop.
        web.onPause()
        browser?.page?.onPause()
        web.pauseTimers()
        phone.stop() // the phone answers Atulya only while the app is open and unlocked
        super.onPause()
    }

    override fun onResume() {
        super.onResume()
        web.onResume()
        browser?.page?.onResume()
        web.resumeTimers()
        if (unlocked && leftAt > 0 && System.currentTimeMillis() - leftAt > relockAfterMs) unlocked = false
        if (!unlocked) unlock() else {
            if (pendingUrl == null && web.url == null) web.loadUrl(origin.toString()) // reopened within the grace period
            openPending()
            phone.start()
        }
    }

    override fun onStop() {
        super.onStop()
        leftAt = System.currentTimeMillis()
        if (unlocked) lastUnlockAt = leftAt // the 2-minute grace counts from leaving the app
        stopRecognition() // never keep listening in the background
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        pendingUrl = linkFrom(intent) ?: pendingUrl
        if (unlocked) openPending()
    }

    /** Only links to the Atulya origin (e.g. the Telegram "tap to sign in" link) open inside the app. */
    private fun linkFrom(intent: Intent?): String? {
        val data = intent?.data ?: return null
        return if (isAtulya(data)) data.toString() else null
    }

    private fun openPending() {
        val url = pendingUrl ?: return
        pendingUrl = null
        closeWebsite()
        val target = Uri.parse(url)
        val handoff = target.getQueryParameter("handoff")
        if (target.path == "/api/auth/google/finish" && handoff != null) {
            val prefs = getSharedPreferences("identity", MODE_PRIVATE)
            val verifier = prefs.getString("google_verifier", null)
            if (verifier == null) {
                Toast.makeText(this, "Start Google sign-in from this Atulya app first", Toast.LENGTH_LONG).show()
                web.loadUrl(origin.toString())
                return
            }
            val body = "handoff=" + URLEncoder.encode(handoff, "UTF-8") + "&verifier=" + URLEncoder.encode(verifier, "UTF-8")
            prefs.edit().remove("google_verifier").apply()
            web.postUrl(origin.toString().trimEnd('/') + "/api/auth/google/app", body.toByteArray(Charsets.UTF_8))
            return
        }
        web.loadUrl(url)
    }

    private fun beginGoogleLogin(target: Uri) {
        if (!isAtulya(target) || target.path != "/api/auth/google/start") return
        val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val flags = Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING
        val verifier = Base64.encodeToString(bytes, flags)
        val proof = Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII)), flags)
        getSharedPreferences("identity", MODE_PRIVATE).edit().putString("google_verifier", verifier).apply()
        web.loadUrl(target.buildUpon().appendQueryParameter("app_challenge", proof).build().toString())
    }

    private fun composeSms(number: String, body: String): Boolean {
        if (!number.matches(Regex("\\+?[0-9]{3,15}")) || body.length > 2000) return false
        try {
            startActivity(Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:$number")).putExtra("sms_body", body))
            return true
        } catch (_: Exception) { Toast.makeText(this, "No SMS app is available", Toast.LENGTH_LONG).show(); return false }
    }

    private fun dial(number: String): Boolean {
        if (!number.matches(Regex("\\+?[0-9]{3,15}"))) return false
        try { startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number"))); return true }
        catch (_: Exception) { Toast.makeText(this, "No phone dialer is available", Toast.LENGTH_LONG).show(); return false }
    }

    private fun scheduleNativeAlarm(alertId: Int, title: String, message: String, triggerAtMillis: Long): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) askFor(Manifest.permission.POST_NOTIFICATIONS)
        return try {
            val alarmManager = getSystemService(ALARM_SERVICE) as? android.app.AlarmManager ?: return false
            val intent = Intent(this, AlarmReceiver::class.java).apply {
                action = "com.atulvij.atulya.ALARM_TRIGGER"
                putExtra("alert_id", alertId)
                putExtra("title", title)
                putExtra("message", message)
            }
            val pendingIntent = PendingIntent.getBroadcast(
                this, alertId, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                alarmManager.setExactAndAllowWhileIdle(android.app.AlarmManager.RTC_WAKEUP, triggerAtMillis, pendingIntent)
            } else {
                alarmManager.setExact(android.app.AlarmManager.RTC_WAKEUP, triggerAtMillis, pendingIntent)
            }
            true
        } catch (_: Exception) { false }
    }

    private fun cancelNativeAlarm(alertId: Int): Boolean {
        return try {
            val alarmManager = getSystemService(ALARM_SERVICE) as? android.app.AlarmManager ?: return false
            val intent = Intent(this, AlarmReceiver::class.java).apply { action = "com.atulvij.atulya.ALARM_TRIGGER" }
            val pendingIntent = PendingIntent.getBroadcast(
                this, alertId, intent,
                PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
            ) ?: return true
            alarmManager.cancel(pendingIntent)
            pendingIntent.cancel()
            true
        } catch (_: Exception) { false }
    }

    private fun playMediaStream(url: String, title: String) {
        val intent = Intent(this, MediaPlaybackService::class.java).apply {
            action = MediaPlaybackService.ACTION_PLAY
            putExtra("url", url)
            putExtra("title", title)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun controlMediaStream(action: String): Boolean {
        if (!MediaPlaybackService.hasPlayableStream) return false
        val intent = Intent(this, MediaPlaybackService::class.java).apply {
            this.action = action
        }
        startService(intent)
        return true
    }

    private fun sendDirectSms(number: String, body: String): Boolean {
        if (!number.matches(Regex("\\+?[0-9]{3,15}")) || body.isEmpty() || body.length > 2000) return false
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            return composeSms(number, body)
        }
        return try {
            val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                getSystemService(android.telephony.SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION")
                android.telephony.SmsManager.getDefault()
            }
            val parts = smsManager.divideMessage(body)
            smsManager.sendMultipartTextMessage(number, null, parts, null, null)
            true
        } catch (_: Exception) { composeSms(number, body) }
    }

    private fun callDirect(number: String): Boolean {
        if (!number.matches(Regex("\\+?[0-9]{3,15}"))) return false
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            return dial(number)
        }
        return try {
            startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")))
            true
        } catch (_: Exception) { dial(number) }
    }

    private fun isAtulya(uri: Uri): Boolean {
        fun port(value: Uri) = if (value.port != -1) value.port else if (value.scheme == "https") 443 else 80
        return uri.scheme == origin.scheme && uri.host == origin.host && port(uri) == port(origin) && uri.userInfo == null
    }

    private fun openWebsite(uri: Uri) {
        if (uri.scheme != "https" || uri.host.isNullOrBlank() || uri.userInfo != null) return
        if (uri.host == "accounts.google.com") {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
            return
        }
        stopRecognition()
        val surface = browser ?: InAppBrowser(this, ::isAtulya, { target ->
            closeWebsite()
            web.loadUrl(target.toString())
        }, { target -> startActivity(Intent(Intent.ACTION_VIEW, target)) }, ::closeWebsite).also {
            browser = it
            content.addView(it, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        }
        surface.open(uri)
    }

    private fun closeWebsite() {
        val surface = browser ?: return
        browser = null
        content.removeView(surface)
        surface.destroy()
    }

    private fun unlock() {
        val allowed = BIOMETRIC_STRONG or DEVICE_CREDENTIAL
        if (BiometricManager.from(this).canAuthenticate(allowed) != BiometricManager.BIOMETRIC_SUCCESS) {
            // No screen lock set up: refuse rather than run unprotected.
            web.loadData("<h3 style='font-family:sans-serif;color:#69eaff;background:#050b12'>" +
                "Set a fingerprint, face or PIN screen lock on this phone to use Atulya.</h3>", "text/html", "utf-8")
            return
        }
        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    unlocked = true
                    phone.start()
                    lastUnlockAt = System.currentTimeMillis()
                    leftAt = 0L
                    if (pendingUrl != null) openPending() else if (web.url == null) web.loadUrl(origin.toString())
                    checkForUpdate()
                }
                override fun onAuthenticationError(code: Int, message: CharSequence) {
                    finish()
                }
            })
        prompt.authenticate(BiometricPrompt.PromptInfo.Builder()
            .setTitle("Unlock Atulya")
            .setSubtitle("Fingerprint, face or screen lock")
            .setAllowedAuthenticators(allowed)
            .build())
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            setGeolocationEnabled(true)
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            allowContentAccess = false
        }
        // Passkeys inside the app (Credential Manager), trusted via /.well-known/assetlinks.json.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_AUTHENTICATION)) {
            WebSettingsCompat.setWebAuthenticationSupport(web.settings, WebSettingsCompat.WEB_AUTHENTICATION_SUPPORT_FOR_APP)
        }
        web.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                if (isAtulya(Uri.parse(url))) cookieWriter.execute { CookieManager.getInstance().flush() }
            }
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return false
                val url = request.url
                if (isAtulya(url)) {
                    if (url.path == "/api/auth/google/start" && url.getQueryParameter("app_challenge") == null) {
                        beginGoogleLogin(url)
                        return true
                    }
                    return false
                }
                if (url.scheme == "https") openWebsite(url)
                else if (request.hasGesture() && url.scheme in setOf("mailto", "tel")) {
                    try { startActivity(Intent(Intent.ACTION_VIEW, url)) } catch (_: Exception) { }
                }
                return true
            }
        }
        // Native voice input: the phone's own recognizer (free, accurate, Hindi, built-in noise handling).
        // Exposed as window.AtulyaNative only to the Atulya origin, never to other pages.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            // The allowed origin must include a non-default port (e.g. the CI test server :8501), or the bridge is missing.
            val allowedOrigin = "${origin.scheme}://${origin.host}" + if (origin.port != -1) ":${origin.port}" else ""
            WebViewCompat.addWebMessageListener(web, "AtulyaNative", setOf(allowedOrigin)) {
                    _, message, _, isMainFrame, reply ->
                if (!isMainFrame) return@addWebMessageListener
                val command = try { JSONObject(message.data ?: "{}") } catch (_: Exception) { JSONObject() }
                voiceReply = reply
                when (command.optString("cmd")) {
                    "listen" -> startRecognition(command.optString("lang", "en-IN"))
                    "stop" -> stopRecognition()
                    "google_login" -> beginGoogleLogin(Uri.parse(command.optString("url")))
                    "compose_sms", "dial" -> {
                        val sms = command.optString("cmd") == "compose_sms"
                        val ok = if (sms) composeSms(command.optString("number"), command.optString("body")) else dial(command.optString("number"))
                        reply.postMessage(JSONObject().put("type", "phone_action").put("id", command.optString("id"))
                            .put("status", if (!ok) "failed" else if (sms) "composer_opened" else "dialer_opened").toString())
                    }
                    "schedule_alarm" -> {
                        val alertId = command.optInt("id", 1001)
                        val title = command.optString("title", "Reminder")
                        val msg = command.optString("message", "")
                        val trigger = command.optLong("time_ms", System.currentTimeMillis() + 60000L)
                        val ok = scheduleNativeAlarm(alertId, title, msg, trigger)
                        reply.postMessage(JSONObject().put("type", "alarm_result").put("id", alertId).put("scheduled", ok).toString())
                    }
                    "cancel_alarm" -> {
                        val alertId = command.optInt("id", 1001)
                        val ok = cancelNativeAlarm(alertId)
                        reply.postMessage(JSONObject().put("type", "alarm_result").put("id", alertId).put("cancelled", ok).toString())
                    }
                    "play_media" -> {
                        val url = command.optString("url")
                        val title = command.optString("title", "Audio Stream")
                        if (url.isNotEmpty()) playMediaStream(url, title)
                    }
                    "pause_media" -> controlMediaStream(MediaPlaybackService.ACTION_PAUSE)
                    "resume_media" -> controlMediaStream(MediaPlaybackService.ACTION_PLAY)
                    "stop_media" -> controlMediaStream(MediaPlaybackService.ACTION_STOP)
                    "send_sms_direct" -> {
                        val ok = sendDirectSms(command.optString("number"), command.optString("body"))
                        reply.postMessage(JSONObject().put("type", "phone_action").put("id", command.optString("id")).put("status", if (ok) "sms_sent" else "failed").toString())
                    }
                    "call_direct" -> {
                        val ok = callDirect(command.optString("number"))
                        reply.postMessage(JSONObject().put("type", "phone_action").put("id", command.optString("id")).put("status", if (ok) "call_placed" else "failed").toString())
                    }
                }
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(requestOrigin: String,
                                                            callback: GeolocationPermissions.Callback) {
                val trusted = Uri.parse(requestOrigin).host == origin.host
                if (!trusted) { callback.invoke(requestOrigin, false, false); return }
                if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.ACCESS_COARSE_LOCATION)
                    == PackageManager.PERMISSION_GRANTED) {
                    callback.invoke(requestOrigin, true, false)
                } else {
                    pendingGeo = requestOrigin to callback // answered in onRequestPermissionsResult
                    ActivityCompat.requestPermissions(this@MainActivity, arrayOf(
                        Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION), 2)
                }
            }

            override fun onPermissionRequest(request: PermissionRequest) {
                val sameOrigin = request.origin.host == origin.host && request.origin.scheme == "https"
                val wanted = request.resources.filter {
                    it == PermissionRequest.RESOURCE_AUDIO_CAPTURE || it == PermissionRequest.RESOURCE_VIDEO_CAPTURE
                }
                if (!sameOrigin || wanted.isEmpty()) { request.deny(); return }
                val missing = wanted.map { mediaPermission(it) }.filter {
                    ContextCompat.checkSelfPermission(this@MainActivity, it) != PackageManager.PERMISSION_GRANTED
                }
                runOnUiThread {
                    if (missing.isEmpty()) request.grant(wanted.toTypedArray())
                    else {
                        pendingMedia?.deny()
                        pendingMedia = request // answered in onRequestPermissionsResult
                        ActivityCompat.requestPermissions(this@MainActivity, missing.toTypedArray(), 3)
                    }
                }
            }
        }
    }

    private fun sendVoice(kind: String, text: String = "") {
        val payload = JSONObject().put("kind", kind).put("text", text).toString()
        runOnUiThread { try { voiceReply?.postMessage(payload) } catch (_: Exception) { } }
    }

    private fun startRecognition(language: String) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            askFor(Manifest.permission.RECORD_AUDIO)
            sendVoice("denied")
            return
        }
        val engine = recognizer ?: SpeechRecognizer.createSpeechRecognizer(this).also { recognizer = it }
        engine.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) = sendVoice("ready")
            override fun onBeginningOfSpeech() = sendVoice("speech")
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() = sendVoice("end")
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
            override fun onResults(results: Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                sendVoice(if (text.isBlank()) "nomatch" else "result", text)
            }
            override fun onError(error: Int) {
                sendVoice(when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "nomatch"
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "denied"
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "busy"
                    else -> "error"
                }, error.toString())
            }
        })
        engine.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 900L)
        })
    }

    private fun stopRecognition() {
        recognizer?.cancel()
    }

    override fun onDestroy() {
        closeWebsite()
        recognizer?.destroy()
        recognizer = null
        cookieWriter.shutdown()
        phone.destroy()
        super.onDestroy()
    }

    /** Native-shell updates: the web UI updates itself; this only offers a newer signed APK. */
    private fun checkForUpdate() {
        Thread {
            try {
                val connection = java.net.URL("${origin}/api/app/latest").openConnection() as java.net.HttpURLConnection
                connection.connectTimeout = 5000
                connection.readTimeout = 5000
                val body = org.json.JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                val latest = body.optString("version")
                val url = body.optString("url")
                if (latest.isNotEmpty() && url.startsWith("https://github.com/") && isNewer(latest, BuildConfig.VERSION_NAME)) {
                    runOnUiThread {
                        androidx.appcompat.app.AlertDialog.Builder(this)
                            .setTitle("Update available")
                            .setMessage("Atulya $latest is ready (you have ${BuildConfig.VERSION_NAME}).")
                            .setPositiveButton("Update") { _, _ -> startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                            .setNegativeButton("Later", null)
                            .show()
                    }
                }
            } catch (_: Exception) { /* offline or no release yet */ }
        }.start()
    }

    private fun isNewer(candidate: String, current: String): Boolean {
        val a = candidate.split(".").map { it.toIntOrNull() ?: 0 }
        val b = current.split(".").map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    @Deprecated("Location answer for the web page's geolocation request")
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        @Suppress("DEPRECATION")
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val locationGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                              ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (locationGranted && pendingGeo != null) {
            pendingGeo?.let { (requestOrigin, callback) -> callback.invoke(requestOrigin, true, false) }
            pendingGeo = null
        } else if (requestCode == 2) {
            val granted = grantResults.any { it == PackageManager.PERMISSION_GRANTED }
            pendingGeo?.let { (requestOrigin, callback) -> callback.invoke(requestOrigin, granted, false) }
            pendingGeo = null
        }
        if (requestCode == 3) {
            pendingMedia?.let { request ->
                val allowed = request.resources.filter {
                    (it == PermissionRequest.RESOURCE_AUDIO_CAPTURE || it == PermissionRequest.RESOURCE_VIDEO_CAPTURE) &&
                        ContextCompat.checkSelfPermission(this, mediaPermission(it)) == PackageManager.PERMISSION_GRANTED
                }
                if (allowed.isNotEmpty()) request.grant(allowed.toTypedArray()) else request.deny()
            }
            pendingMedia = null
        }
    }

    /** Ask only for what the feature in use needs, at the moment it needs it (nothing is asked on first launch).
     *  Location is asked by the page's geolocation request; SMS and calls fall back to the SMS app and dialer. */
    private fun askFor(vararg permissions: String) {
        val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) runOnUiThread { ActivityCompat.requestPermissions(this, missing.toTypedArray(), 1) }
    }

    private fun mediaPermission(resource: String) =
        if (resource == PermissionRequest.RESOURCE_VIDEO_CAPTURE) Manifest.permission.CAMERA else Manifest.permission.RECORD_AUDIO

    /** Back first closes whatever is open in Atulya (menu, dialog, conversation mode); only then leaves. */
    @Deprecated("Back navigation inside the web app")
    override fun onBackPressed() {
        browser?.let { surface ->
            surface.navigateBack()
            return
        }
        web.evaluateJavascript("(window.atulyaBack && window.atulyaBack()) ? 'handled' : 'none'") { result ->
            if (result?.contains("handled") == true) return@evaluateJavascript
            if (web.canGoBack()) web.goBack() else {
                @Suppress("DEPRECATION")
                super.onBackPressed()
            }
        }
    }
}
