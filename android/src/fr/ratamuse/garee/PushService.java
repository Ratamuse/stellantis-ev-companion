package fr.ratamuse.garee;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/**
 * Connexion permanente au serveur pour recevoir les notifications en quelques secondes (comme ntfy, sans tiers) :
 * appels longs enchaines sur /api/notifs/wait. Android impose une notification "e-208 connecte", reglee au minimum.
 */
public class PushService extends Service {
    private static final String CHANNEL = "connexion";
    private static final int WAIT_S = 50;
    private volatile boolean running;
    private Thread loop;

    static void start(Context ctx) {
        try {
            ctx.startForegroundService(new Intent(ctx, PushService.class));
        } catch (Exception ignored) {
            // demarrage refuse en arriere-plan : il sera relance a la prochaine ouverture de l'appli
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Notification n = notification();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(2, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(2, n);
        }
        if (loop == null || !loop.isAlive()) {
            running = true;
            loop = new Thread(this::listen, "notifications");
            loop.start();
        }
        return START_STICKY; // relance par Android s'il doit l'arreter
    }

    private void listen() {
        long pause = 5_000;
        while (running) {
            if (Notifier.fetch(this, WAIT_S)) {
                pause = 5_000;
            } else { // pas de reseau, Tailscale coupe, serveur arrete : on reessaie de plus en plus espace
                try {
                    Thread.sleep(pause);
                } catch (InterruptedException e) {
                    return;
                }
                pause = Math.min(pause * 2, 300_000);
            }
        }
    }

    @Override
    public void onDestroy() {
        running = false;
        if (loop != null) {
            loop.interrupt();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }

    private Notification notification() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        NotificationChannel ch = new NotificationChannel(CHANNEL, Tr.t("Connexion au serveur"), NotificationManager.IMPORTANCE_MIN);
        ch.setShowBadge(false);
        nm.createNotificationChannel(ch);
        return new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_lock_idle_charging)
                .setContentTitle(String.format(Tr.t("%s connecté"), getApplicationInfo().loadLabel(getPackageManager())))
                .setContentText(Tr.t("Réception des notifications en direct"))
                .setOngoing(true)
                .build();
    }
}
