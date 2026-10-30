package `in`.waterinnovation.commercialdocuments

import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.print.PrintManager
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private var pendingDownload: PendingDownload? = null
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(9, 42, 57)
        window.navigationBarColor = Color.rgb(245, 248, 247)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        }

        webView = WebView(this).apply {
            setBackgroundColor(Color.WHITE)
            overScrollMode = View.OVER_SCROLL_NEVER
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                allowFileAccess = false
                allowContentAccess = true
                javaScriptCanOpenWindowsAutomatically = false
                setSupportMultipleWindows(false)
                loadWithOverviewMode = true
                useWideViewPort = true
            }
            addJavascriptInterface(PrintBridge(), "CommercialDocuments")
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    request: WebResourceRequest
                ): Boolean = handleNavigation(request.url)

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError
                ) {
                    super.onReceivedError(view, request, error)
                    if (request.isForMainFrame) {
                        Toast.makeText(
                            this@MainActivity,
                            R.string.page_load_error,
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }

                override fun onPageFinished(view: WebView, url: String) {
                    super.onPageFinished(view, url)
                    if (isWebsiteUrl(Uri.parse(url))) {
                        view.evaluateJavascript(
                            "window.print=function(){window.CommercialDocuments.printPage();};",
                            null
                        )
                    }
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    view: WebView,
                    callback: ValueCallback<Array<Uri>>,
                    params: FileChooserParams
                ): Boolean {
                    if (filePathCallback != null) {
                        filePathCallback?.onReceiveValue(null)
                    }
                    filePathCallback = callback
                    return try {
                        startActivityForResult(
                            params.createIntent(),
                            FILE_CHOOSER_REQUEST_CODE
                        )
                        true
                    } catch (_: ActivityNotFoundException) {
                        filePathCallback = null
                        callback.onReceiveValue(null)
                        Toast.makeText(
                            this@MainActivity,
                            R.string.file_picker_unavailable,
                            Toast.LENGTH_LONG
                        ).show()
                        true
                    }
                }
            }
            setDownloadListener { url, _, contentDisposition, mimeType, _ ->
                requestDownload(url, contentDisposition, mimeType)
            }
        }
        setContentView(webView)
        webView.loadUrl(WEBSITE_HOME_URL)
    }

    @Deprecated("Deprecated in Android; retained for API 23 compatibility.")
    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    @Deprecated("Deprecated in Android; retained for the system file picker.")
    @Suppress("DEPRECATION")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FILE_CHOOSER_REQUEST_CODE) {
            filePathCallback?.onReceiveValue(
                WebChromeClient.FileChooserParams.parseResult(resultCode, data)
            )
            filePathCallback = null
        }
    }

    @Deprecated("Deprecated in Android; retained for API 23 compatibility.")
    @Suppress("DEPRECATION")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != DOWNLOAD_PERMISSION_REQUEST_CODE) return

        val download = pendingDownload
        pendingDownload = null
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED && download != null) {
            enqueueDownload(download)
        } else {
            Toast.makeText(this, R.string.download_permission_denied, Toast.LENGTH_LONG).show()
        }
    }

    override fun onDestroy() {
        if (::webView.isInitialized) {
            webView.removeJavascriptInterface("CommercialDocuments")
            webView.webChromeClient = null
            webView.webViewClient = WebViewClient()
            (webView.parent as? ViewGroup)?.removeView(webView)
            webView.destroy()
        }
        filePathCallback?.onReceiveValue(null)
        filePathCallback = null
        super.onDestroy()
    }

    private fun handleNavigation(uri: Uri): Boolean {
        if (isWebsiteUrl(uri)) return false
        if (uri.scheme !in setOf("https", "http", "mailto", "tel")) return true

        return try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
            true
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.no_browser_available, Toast.LENGTH_LONG).show()
            true
        }
    }

    private fun isWebsiteUrl(uri: Uri): Boolean =
        uri.scheme == "https" &&
            uri.host == WEBSITE_HOST &&
            (uri.port == -1 || uri.port == 443) &&
            uri.path?.startsWith(WEBSITE_PATH_PREFIX) == true

    private fun requestDownload(url: String, contentDisposition: String?, mimeType: String?) {
        val uri = Uri.parse(url)
        if (uri.scheme != "https" || uri.host.isNullOrBlank()) {
            Toast.makeText(this, R.string.download_unavailable, Toast.LENGTH_LONG).show()
            return
        }

        val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
        val download = PendingDownload(url, fileName, mimeType)
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P &&
            checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            pendingDownload = download
            requestPermissions(
                arrayOf(android.Manifest.permission.WRITE_EXTERNAL_STORAGE),
                DOWNLOAD_PERMISSION_REQUEST_CODE
            )
            return
        }
        enqueueDownload(download)
    }

    private fun enqueueDownload(download: PendingDownload) {
        try {
            val request = DownloadManager.Request(Uri.parse(download.url))
                .setTitle(download.fileName)
                .setDescription(getString(R.string.download_started))
                .setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
                )
                .setDestinationInExternalPublicDir(
                    Environment.DIRECTORY_DOWNLOADS,
                    download.fileName
                )
            download.mimeType?.takeIf(String::isNotBlank)?.let(request::setMimeType)
            CookieManager.getInstance().getCookie(download.url)
                ?.takeIf(String::isNotBlank)
                ?.let { request.addRequestHeader("Cookie", it) }

            val manager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            manager.enqueue(request)
            Toast.makeText(this, R.string.download_started, Toast.LENGTH_LONG).show()
        } catch (_: IllegalArgumentException) {
            Toast.makeText(this, R.string.download_unavailable, Toast.LENGTH_LONG).show()
        } catch (_: SecurityException) {
            Toast.makeText(this, R.string.download_permission_denied, Toast.LENGTH_LONG).show()
        }
    }

    private fun printDocument() {
        try {
            val printManager = getSystemService(Context.PRINT_SERVICE) as PrintManager
            printManager.print(
                getString(R.string.print_job_name),
                webView.createPrintDocumentAdapter(getString(R.string.print_job_name)),
                null
            )
        } catch (error: IllegalStateException) {
            Toast.makeText(
                this,
                getString(R.string.print_unavailable, error.localizedMessage.orEmpty()),
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private inner class PrintBridge {
        @JavascriptInterface
        fun printPage() {
            runOnUiThread { printDocument() }
        }
    }

    private data class PendingDownload(
        val url: String,
        val fileName: String,
        val mimeType: String?
    )

    private companion object {
        const val WEBSITE_HOST = "water-innovation-systems.github.io"
        const val WEBSITE_PATH_PREFIX = "/commercial-documents.co.in/"
        const val WEBSITE_HOME_URL =
            "https://water-innovation-systems.github.io/commercial-documents.co.in/index.html"
        const val FILE_CHOOSER_REQUEST_CODE = 1001
        const val DOWNLOAD_PERMISSION_REQUEST_CODE = 1002
    }
}
