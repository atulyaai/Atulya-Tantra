package com.atulvij.atulya

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class SmsReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "AtulyaSmsReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        val fullBody = StringBuilder()
        var sender = ""

        for (sms in messages) {
            fullBody.append(sms.displayMessageBody)
            if (sender.isEmpty()) {
                sender = sms.displayOriginatingAddress ?: ""
            }
        }

        val text = fullBody.toString()
        val textLower = text.lowercase()

        // Filter for bank and transaction patterns
        val isTransaction = textLower.contains("rs.") || textLower.contains("inr") ||
                textLower.contains("debited") || textLower.contains("spent") || textLower.contains("paid")

        if (!isTransaction) return

        Log.i(TAG, "Transaction SMS detected from $sender. Dispatching to Atulya expense parser.")

        val prefs = context.getSharedPreferences("atulya_prefs", Context.MODE_PRIVATE)
        val serverUrl = prefs.getString("server_url", "https://atulya.atulvij.com") ?: "https://atulya.atulvij.com"
        val sessionCookie = prefs.getString("session_cookie", "") ?: ""

        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val url = URL("$serverUrl/api/expenses/parse-sms")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                if (sessionCookie.isNotEmpty()) {
                    conn.setRequestProperty("Cookie", sessionCookie)
                }
                conn.doOutput = true
                conn.connectTimeout = 10000
                conn.readTimeout = 10000

                val payload = JSONObject().apply {
                    put("sms_text", text)
                }

                conn.outputStream.use { os ->
                    os.write(payload.toString().toByteArray())
                }

                val responseCode = conn.responseCode
                Log.i(TAG, "Expense parse-sms response code: $responseCode")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to dispatch SMS to Atulya server: ${e.message}")
            } finally {
                pendingResult.finish()
            }
        }
    }
}
