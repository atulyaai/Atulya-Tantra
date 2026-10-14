package com.atulvij.atulya

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            // Restore alarms or sync reminders from local storage on device restart
            val prefs = context.getSharedPreferences("atulya_alarms", Context.MODE_PRIVATE)
            val stored = prefs.all
            // In a full sync, query active reminder timestamps and re-register
        }
    }
}
