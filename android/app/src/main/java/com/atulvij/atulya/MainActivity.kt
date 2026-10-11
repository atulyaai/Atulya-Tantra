package com.atulvij.atulya

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.view.WindowManager
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
import androidx.webkit.WebSettingsCompat
import androidx.webkit.WebViewFeature

/**
 * Atulya for Android.
 *
 * Security: the app is locked with fingerprint/face (or the device PIN) every time it comes
 * to the foreground; screenshots and the recent-apps preview are blocked; only the
 * configured Atulya origin is loaded inside the app (other links open in the browser);
 * the WebView gets microphone/camera only for that origin and only after Android grants them.
 */
class MainActivity : AppCompatActivity() {
    private lateinit var web: WebView
    private var unlocked = false
    private val origin: Uri = Uri.parse(BuildConfig.ATULYA_URL)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        web = WebView(this)
        setContentView(web)
        configureWebView()
        requestMediaPermissions()
    }

    override fun onResume() {
        super.onResume()
        if (!unlocked) unlock()
    }

    override fun onStop() {
        super.onStop()
        unlocked = false // lock again whenever the app leaves the screen
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
                    if (web.url == null) web.loadUrl(origin.toString())
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
                val url = request.url
                if (url.scheme == origin.scheme && url.host == origin.host) return false
                startActivity(Intent(Intent.ACTION_VIEW, url)) // anything else opens outside the app
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
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

    private fun requestMediaPermissions() {
        val missing = arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA).filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) ActivityCompat.requestPermissions(this, missing.toTypedArray(), 1)
    }

    @Deprecated("Back navigation inside the web app")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
