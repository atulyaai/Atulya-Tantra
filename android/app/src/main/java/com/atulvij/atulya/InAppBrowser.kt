package com.atulvij.atulya

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import android.os.Message
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** Third-party pages never receive the Atulya native bridge, files, camera or microphone. */
@SuppressLint("SetJavaScriptEnabled")
class InAppBrowser(
    context: Context,
    private val isAtulya: (Uri) -> Boolean,
    private val openAtulya: (Uri) -> Unit,
    private val openAuthentication: (Uri) -> Unit,
    private val onClose: () -> Unit
) : LinearLayout(context) {
    private val pages = mutableListOf<WebView>()
    val page: WebView get() = pages.last()
    private val address = TextView(context)

    init {
        orientation = VERTICAL
        setBackgroundColor(Color.rgb(5, 11, 18))
        val toolbar = LinearLayout(context).apply { orientation = HORIZONTAL }
        val back = Button(context).apply {
            text = "Back"
            contentDescription = "Previous website page"
            setOnClickListener { navigateBack() }
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
        showPage(newPage())
    }

    private fun showPage(next: WebView) {
        pages.lastOrNull()?.let { previous -> previous.onPause(); removeView(previous) }
        pages.add(next)
        addView(next, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))
        next.onResume()
    }

    private fun newPage(): WebView {
        val surface = WebView(context)
        surface.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setGeolocationEnabled(false)
            setSupportMultipleWindows(true)
            javaScriptCanOpenWindowsAutomatically = false
            mediaPlaybackRequiresUserGesture = true
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }
        surface.webChromeClient = object : WebChromeClient() {
            override fun onCreateWindow(view: WebView, isDialog: Boolean, isUserGesture: Boolean, resultMsg: Message): Boolean {
                if (!isUserGesture || pages.size >= 4) return false
                val transport = resultMsg.obj as? WebView.WebViewTransport ?: return false
                // Keep the actual popup WebView: reloading its URL would discard a form's POST body.
                val popup = newPage()
                showPage(popup)
                address.text = "Opening website"
                transport.webView = popup
                resultMsg.sendToTarget()
                return true
            }
            override fun onCloseWindow(window: WebView) {
                if (pages.lastOrNull() === window && pages.size > 1) closePopup()
            }
            override fun onPermissionRequest(request: PermissionRequest) = request.deny()
            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                callback.invoke(origin, false, false)
            }
        }
        surface.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return false
                val uri = request.url
                if (isAtulya(uri)) { openAtulya(uri); return true }
                if (!allowed(uri)) return true
                // Google OAuth requires the system browser; ordinary pages stay inside Atulya.
                if (uri.host == "accounts.google.com") { openAuthentication(uri); return true }
                return false
            }
            override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                if (url != "about:blank" && !allowed(Uri.parse(url))) view.stopLoading()
                if (pages.lastOrNull() === view) address.text = Uri.parse(url).host ?: "Website"
            }
            override fun onPageFinished(view: WebView, url: String) {
                if (pages.lastOrNull() === view) address.text = Uri.parse(url).host ?: "Website"
            }
        }
        return surface
    }

    private fun allowed(uri: Uri): Boolean = uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null

    fun open(uri: Uri) {
        if (isAtulya(uri)) { openAtulya(uri); return }
        if (!allowed(uri)) return
        if (uri.host == "accounts.google.com") { openAuthentication(uri); return }
        address.text = uri.host
        page.loadUrl(uri.toString())
    }

    fun navigateBack() {
        if (page.canGoBack()) page.goBack()
        else if (pages.size > 1) closePopup()
        else onClose()
    }

    private fun closePopup() {
        val popup = pages.removeAt(pages.lastIndex)
        removeView(popup)
        popup.stopLoading()
        popup.destroy()
        addView(page, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))
        page.onResume()
        address.text = page.url?.let { Uri.parse(it).host } ?: "Website"
    }

    fun destroy() {
        pages.forEach { surface -> removeView(surface); surface.stopLoading(); surface.destroy() }
        pages.clear()
    }
}
