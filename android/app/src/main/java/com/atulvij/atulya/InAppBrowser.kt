package com.atulvij.atulya

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.net.Uri
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** Third-party browsing surface. No Atulya native bridge, file access, camera or microphone. */
@SuppressLint("SetJavaScriptEnabled")
class InAppBrowser(
    context: Context,
    private val isAtulya: (Uri) -> Boolean,
    private val openAtulya: (Uri) -> Unit,
    private val openAuthentication: (Uri) -> Unit,
    onClose: () -> Unit
) : LinearLayout(context) {
    val page = WebView(context)
    private val address = TextView(context)

    init {
        orientation = VERTICAL
        setBackgroundColor(Color.rgb(5, 11, 18))
        val toolbar = LinearLayout(context).apply { orientation = HORIZONTAL }
        val back = Button(context).apply {
            text = "Back"
            contentDescription = "Previous website page"
            setOnClickListener { if (page.canGoBack()) page.goBack() else onClose() }
        }
        val close = Button(context).apply {
            text = "Atulya"
            contentDescription = "Close website and return to Atulya"
            setOnClickListener { onClose() }
        }
        address.setTextColor(Color.WHITE)
        address.setPadding(12, 12, 12, 12)
        address.maxLines = 2
        toolbar.addView(back)
        toolbar.addView(address, LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f))
        toolbar.addView(close)
        addView(toolbar)
        addView(page, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))
        page.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setGeolocationEnabled(false)
            setSupportMultipleWindows(true)
            javaScriptCanOpenWindowsAutomatically = false
            mediaPlaybackRequiresUserGesture = true
        }
        page.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) = request.deny()
            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                callback.invoke(origin, false, false)
            }
        }
        page.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return false
                val uri = request.url
                if (isAtulya(uri)) { openAtulya(uri); return true }
                if (uri.scheme != "https" || uri.host.isNullOrBlank() || uri.userInfo != null) return true
                // Google OAuth disallows embedded user agents. Keep its sign-in in the system browser.
                if (uri.host == "accounts.google.com") { openAuthentication(uri); return true }
                return false
            }
            override fun onPageFinished(view: WebView, url: String) {
                address.text = Uri.parse(url).host ?: "Website"
            }
        }
    }

    fun open(uri: Uri) {
        if (uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null) {
            address.text = uri.host
            page.loadUrl(uri.toString())
        }
    }

    fun destroy() {
        page.stopLoading()
        removeView(page)
        page.destroy()
    }
}
