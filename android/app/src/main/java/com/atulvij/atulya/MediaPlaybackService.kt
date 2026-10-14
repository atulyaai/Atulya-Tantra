package com.atulvij.atulya

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

class MediaPlaybackService : Service() {
    companion object {
        const val CHANNEL_ID = "atulya_media_channel"
        const val NOTIFICATION_ID = 2001
        const val ACTION_PLAY = "com.atulvij.atulya.ACTION_PLAY"
        const val ACTION_PAUSE = "com.atulvij.atulya.ACTION_PAUSE"
        const val ACTION_STOP = "com.atulvij.atulya.ACTION_STOP"
    }

    private var mediaPlayer: MediaPlayer? = null
    private var currentTitle: String = "Atulya Media"

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_PLAY -> {
                val url = intent.getStringExtra("url")
                val title = intent.getStringExtra("title") ?: "Atulya Media"
                currentTitle = title
                if (url != null) {
                    playStream(url)
                } else {
                    mediaPlayer?.start()
                    updateNotification(isPlaying = true)
                }
            }
            ACTION_PAUSE -> {
                mediaPlayer?.pause()
                updateNotification(isPlaying = false)
            }
            ACTION_STOP -> {
                stopPlayback()
            }
        }
        return START_NOT_STICKY
    }

    private fun playStream(url: String) {
        mediaPlayer?.release()
        mediaPlayer = MediaPlayer().apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .build()
            )
            setDataSource(url)
            setOnPreparedListener {
                it.start()
                updateNotification(isPlaying = true)
            }
            setOnCompletionListener {
                stopPlayback()
            }
            prepareAsync()
        }
        startForeground(NOTIFICATION_ID, buildNotification(isPlaying = true))
    }

    private fun stopPlayback() {
        mediaPlayer?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Atulya Audio Playback",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Background audio and music controls for Atulya"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(isPlaying: Boolean): android.app.Notification {
        val launchIntent = Intent(this, MainActivity::class.java)
        val pendingLaunch = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val toggleAction = if (isPlaying) ACTION_PAUSE else ACTION_PLAY
        val toggleTitle = if (isPlaying) "Pause" else "Play"
        val toggleIntent = Intent(this, MediaPlaybackService::class.java).apply { action = toggleAction }
        val pendingToggle = PendingIntent.getService(
            this, 1, toggleIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = Intent(this, MediaPlaybackService::class.java).apply { action = ACTION_STOP }
        val pendingStop = PendingIntent.getService(
            this, 2, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("Playing Media")
            .setContentText(currentTitle)
            .setContentIntent(pendingLaunch)
            .addAction(if (isPlaying) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play, toggleTitle, pendingToggle)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", pendingStop)
            .setOngoing(isPlaying)
            .build()
    }

    private fun updateNotification(isPlaying: Boolean) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(isPlaying))
    }

    override fun onDestroy() {
        mediaPlayer?.release()
        mediaPlayer = null
        super.onDestroy()
    }
}
