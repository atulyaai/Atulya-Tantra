package com.atulvij.atulya

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
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
    private var voiceReply: JavaScriptReplyProxy? = null

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
        if (savedInstanceState != null) web.restoreState(savedInstanceState)
        pendingUrl = linkFrom(intent)
        requestMediaPermissions()
    }

    override fun onPause() {
        // Battery: in the background the page, its timers, the 3D scene and any location request all stop.
        web.onPause()
        browser?.page?.onPause()
        web.pauseTimers()
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
        return if (data.scheme == "https" && data.host == origin.host) data.toString() else null
    }

    private fun openPending() {
        val url = pendingUrl ?: return
        pendingUrl = null
        closeWebsite()
        web.loadUrl(url)
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
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return false
                val url = request.url
                if (isAtulya(url)) return false
                if (url.scheme == "https") openWebsite(url)
                else if (request.hasGesture() && url.scheme in setOf("mailto", "tel")) {
                    try { startActivity(Intent(Intent.ACTION_VIEW, url)) } catch (_: Exception) { }
                }
                return true
            }
        }
        // Native voice input: the phone's own recognizer (free, accurate, Hindi, built-in noise handling).
        // Exposed as window.AtulyaNative only to the Atulya origin, never to other pages.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER) &&
            SpeechRecognizer.isRecognitionAvailable(this)) {
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
                if (sameOrigin && wanted.isNotEmpty()) runOnUiThread { request.grant(wanted.toTypedArray()) }
                else request.deny()
            }
        }
    }

    private fun sendVoice(kind: String, text: String = "") {
        val payload = JSONObject().put("kind", kind).put("text", text).toString()
        runOnUiThread { try { voiceReply?.postMessage(payload) } catch (_: Exception) { } }
    }

    private fun startRecognition(language: String) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestMediaPermissions()
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
        if (requestCode == 2) {
            val granted = grantResults.any { it == PackageManager.PERMISSION_GRANTED }
            pendingGeo?.let { (requestOrigin, callback) -> callback.invoke(requestOrigin, granted, false) }
            pendingGeo = null
        }
    }

    private fun requestMediaPermissions() {
        val missing = arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA).filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) ActivityCompat.requestPermissions(this, missing.toTypedArray(), 1)
    }

    /** Back first closes whatever is open in Atulya (menu, dialog, conversation mode); only then leaves. */
    @Deprecated("Back navigation inside the web app")
    override fun onBackPressed() {
        browser?.let { surface ->
            if (surface.page.canGoBack()) surface.page.goBack() else closeWebsite()
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
