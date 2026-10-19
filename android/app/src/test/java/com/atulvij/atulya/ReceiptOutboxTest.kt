package com.atulvij.atulya

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class ReceiptOutboxTest {
    private fun receipt(id: String) = JSONObject().put("id", id).put("success", true).put("output", "done")

    @Test fun lostResponseSurvivesRestartAndRetriesIdenticalReceipt() {
        var disk = "[]"
        val outbox = ReceiptOutbox({ disk }, { disk = it; true })
        outbox.record(receipt("once"))
        var accepted: String? = null
        try {
            outbox.flush { accepted = it.toString(); throw IOException("response lost after server commit") }
            fail("Expected a network failure")
        } catch (_: IOException) { }
        val restarted = ReceiptOutbox({ disk }, { disk = it; true })
        assertTrue(restarted.flush { assertEquals(accepted, it.toString()); true })
        assertEquals("[]", disk)
    }

    @Test fun rejectedReceiptBlocksFurtherUploadsAndRemainsDurable() {
        var disk = "[]"
        val outbox = ReceiptOutbox({ disk }, { disk = it; true })
        outbox.record(receipt("first"))
        outbox.record(receipt("second"))
        var calls = 0
        assertFalse(outbox.flush { calls++; false })
        assertEquals(1, calls)
        val ids = mutableListOf<String>()
        assertTrue(outbox.flush { ids.add(it.getString("id")); true })
        assertEquals(listOf("first", "second"), ids)
    }

    @Test fun duplicateJobDoesNotReplaceOriginalReceipt() {
        var disk = "[]"
        val outbox = ReceiptOutbox({ disk }, { disk = it; true })
        outbox.record(receipt("same"))
        outbox.record(receipt("same").put("success", false))
        var calls = 0
        assertTrue(outbox.flush { calls++; assertTrue(it.getBoolean("success")); true })
        assertEquals(1, calls)
    }
}
