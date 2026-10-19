package com.atulvij.atulya

import org.json.JSONArray
import org.json.JSONObject

/** Retry receipts, never the phone action. Save before attempting the network. */
class ReceiptOutbox(private val read: () -> String, private val write: (String) -> Boolean) {
    companion object { private val lock = Any() }
    fun record(receipt: JSONObject): Unit = synchronized(lock) {
        val pending = JSONArray(read())
        for (index in 0 until pending.length()) {
            if (pending.getJSONObject(index).getString("id") == receipt.getString("id")) return@synchronized
        }
        pending.put(receipt)
        check(write(pending.toString())) { "Could not persist the execution receipt" }
    }

    fun flush(send: (JSONObject) -> Boolean): Boolean = synchronized(lock) {
        val pending = JSONArray(read())
        while (pending.length() > 0) {
            if (!send(pending.getJSONObject(0))) return@synchronized false
            pending.remove(0)
            check(write(pending.toString())) { "Could not persist receipt acknowledgement" }
        }
        true
    }
}
