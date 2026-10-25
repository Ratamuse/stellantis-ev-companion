package fr.ratamuse.garee;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.SystemClock;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Notifications du serveur affichees par l'appli (sans ntfy) : toutes les ~10 minutes, l'appli demande au serveur
 * les nouvelles notifications (GET <serveur>/api/notifs?after=<dernier id>) et les affiche.
 */
final class Notifier {
    private static final long EVERY_MS = 10 * 60_000;
    private static final String ALERTS = "alertes";
    private static final String INFOS = "infos";

    private Notifier() {
    }

    /** Programme la prochaine verification, meme telephone en veille (Android limite a une fois toutes les ~10 min). */
    static void schedule(Context ctx) {
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        PendingIntent pi = PendingIntent.getBroadcast(ctx, 0, new Intent(ctx, NotifReceiver.class),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        am.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + EVERY_MS, pi);
    }

    /** Recupere et affiche les nouvelles notifications (a appeler hors du fil de l'ecran). */
    static void poll(Context ctx) {
        fetch(ctx, 0);
    }

    /**
     * Demande les nouvelles notifications. wait > 0 : appel long, le serveur ne repond qu'a l'arrivee d'une
     * notification ou apres `wait` secondes (connexion permanente, voir PushService). Renvoie false si injoignable.
     */
    static boolean fetch(Context ctx, int wait) {
        SharedPreferences p = ctx.getSharedPreferences(Sender.PREFS, Context.MODE_PRIVATE);
        long after = Math.max(p.getLong("notif_last", -1), 0);
        String base = p.getString("server", Sender.DEFAULT_SERVER);
        String url = wait > 0 ? base + "/api/notifs/wait?timeout=" + wait + "&after=" + after
                : base + "/api/notifs?after=" + after;
        try {
            handle(ctx, get(url, wait > 0 ? (wait + 20) * 1000 : 10_000));
            return true;
        } catch (Exception e) {
            return false; // serveur injoignable (Tailscale coupe, pas de reseau) : nouvel essai plus tard
        }
    }

    private static synchronized void handle(Context ctx, JSONObject r) throws Exception {
        SharedPreferences p = ctx.getSharedPreferences(Sender.PREFS, Context.MODE_PRIVATE);
        long saved = p.getLong("notif_last", -1);
        if (saved >= 0) { // au tout premier passage, on n'affiche pas les anciennes notifications
            JSONArray items = r.getJSONArray("items");
            for (int i = 0; i < items.length(); i++) {
                JSONObject n = items.getJSONObject(i);
                if (n.getLong("id") > saved) { // deja affichee par l'autre canal sinon
                    show(ctx, n.getLong("id"), n.optString("title"), n.optString("message"), n.optInt("priority", 3));
                }
            }
        }
        p.edit().putLong("notif_last", Math.max(saved, r.getLong("last"))).apply();
    }

    private static void show(Context ctx, long id, String title, String message, int priority) {
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(ALERTS, Tr.t("Alertes"), NotificationManager.IMPORTANCE_HIGH));
        nm.createNotificationChannel(new NotificationChannel(INFOS, Tr.t("Informations"), NotificationManager.IMPORTANCE_DEFAULT));
        Intent show = new Intent(ctx, MainActivity.class) // l'appli s'ouvre sur le message complet
                .putExtra("notif_title", title).putExtra("notif_message", message)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent open = PendingIntent.getActivity(ctx, (int) (id % Integer.MAX_VALUE), show,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(ctx, priority >= 4 ? ALERTS : INFOS)
                .setSmallIcon(android.R.drawable.ic_lock_idle_charging)
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(new Notification.BigTextStyle().bigText(message))
                .setContentIntent(open)
                .setAutoCancel(true)
                .build();
        nm.notify((int) (id % Integer.MAX_VALUE), n);
    }

    private static JSONObject get(String url, int readTimeoutMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(10_000);
        c.setReadTimeout(readTimeoutMs);
        try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            for (int n; (n = in.read(buf)) > 0; ) {
                out.write(buf, 0, n);
            }
            return new JSONObject(new String(out.toByteArray(), StandardCharsets.UTF_8));
        } finally {
            c.disconnect();
        }
    }
}
