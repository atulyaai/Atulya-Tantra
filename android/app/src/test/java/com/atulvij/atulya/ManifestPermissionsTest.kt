package com.atulvij.atulya

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The app must never ask for the SMS or call permissions that Play Protect and Google Play treat as
 * restricted. Sending a message or starting a call goes through the phone's own SMS app or dialer, and
 * that tap is the approval. A build that quietly adds the permissions back is a regression.
 */
class ManifestPermissionsTest {

    /** Find a file in the module by walking up from the test working directory. */
    private fun moduleFile(relative: String): File {
        var dir: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (dir != null) {
            val candidate = File(dir, relative)
            if (candidate.isFile) return candidate
            dir = dir.parentFile
        }
        throw IllegalStateException("$relative not found from the test working directory")
    }

    @Test
    fun noRestrictedSmsOrCallPermissions() {
        val text = moduleFile("src/main/AndroidManifest.xml").readText()
        for (permission in listOf(
            "android.permission.SEND_SMS",
            "android.permission.READ_SMS",
            "android.permission.CALL_PHONE",
            "android.permission.CALL_LOG",
        )) {
            assertFalse("$permission must not be declared in AndroidManifest.xml", text.contains(permission))
        }
    }

    @Test
    fun phoneMessagesArePreparedNotSentSilently() {
        val text = moduleFile("src/main/java/com/atulvij/atulya/PhoneAgent.kt").readText()
        assertFalse("the phone agent must not send SMS through SmsManager", text.contains("SmsManager"))
        assertTrue("an SMS result must say it is sent only when the person taps send",
            text.contains("sent only when you tap send"))
        assertTrue("a call result must say the call starts when the person taps call",
            text.contains("the call starts when you tap call"))
    }
}
