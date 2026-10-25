package fr.ratamuse.garee;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.HandlerThread;
import android.os.IBinder;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Trace du trajet : tant que le telephone est connecte au Bluetooth de la voiture, un point GPS toutes les 30 s,
 * envoye au serveur par paquets (POST <serveur>/api/track). Le GPS est coupe des la deconnexion.
 */
public class TrackService extends Service implements LocationListener {
    private static final String CHANNEL = "trajet";
    private static final long FLUSH_MS = 120_000;
    private static TrackService running;

    private final List<double[]> points = new ArrayList<>(); // t (s), lat, lon, precision (m)
    private LocationManager lm;
    private HandlerThread thread;
    private String trip;
    private long lastFlush;

    static void begin(Context ctx, String trip) {
        Intent i = new Intent(ctx, TrackService.class).putExtra("trip", trip);
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.startForegroundService(i);
        } else {
            ctx.startService(i);
        }
    }

    /** Fin de trajet : coupe le GPS, envoie les derniers points (appele depuis un fil d'arriere-plan). */
    static void finish(Context ctx) {
        TrackService s = running;
        if (s != null) {
            s.stopGps();
            s.flush();
        } else {
            sendPending(ctx); // paquets restes en attente d'un trajet precedent
        }
        ctx.stopService(new Intent(ctx, TrackService.class));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (running == this && trip != null) {
            return START_NOT_STICKY; // deja en route
        }
        trip = intent != null && intent.getStringExtra("trip") != null
                ? intent.getStringExtra("trip") : String.valueOf(System.currentTimeMillis() / 1000);
        running = this;
        lastFlush = System.currentTimeMillis();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
        } else {
            startForeground(1, notification());
        }
        thread = new HandlerThread("trajet");
        thread.start();
        lm = getSystemService(LocationManager.class);
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 30_000, 30, this, thread.getLooper());
        } catch (SecurityException e) {
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    @Override
    public void onLocationChanged(Location l) {
        synchronized (points) {
            points.add(new double[]{l.getTime() / 1000.0, l.getLatitude(), l.getLongitude(), l.getAccuracy()});
        }
        if (System.currentTimeMillis() - lastFlush > FLUSH_MS) {
            lastFlush = System.currentTimeMillis();
            flush(); // deja sur le fil "trajet", pas sur l'ecran
        }
    }

    @Override
    public void onStatusChanged(String s, int i, Bundle b) {
    }

    @Override
    public void onProviderEnabled(String s) {
    }

    @Override
    public void onProviderDisabled(String s) {
    }

    @Override
    public void onDestroy() {
        stopGps();
        if (running == this) {
            running = null;
        }
        if (thread != null) {
            thread.quitSafely();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }

    private void stopGps() {
        if (lm != null) {
            lm.removeUpdates(this);
        }
    }

    /** Envoie les points accumules ; en cas d'echec (pas de reseau), ils sont gardes pour plus tard. */
    private void flush() {
        JSONArray pts = new JSONArray();
        synchronized (points) {
            for (double[] p : points) {
                JSONArray a = new JSONArray();
                for (double v : p) {
                    try {
                        a.put(v);
                    } catch (Exception ignored) {
                        // valeur non finie : ignoree
                    }
                }
                pts.put(a);
            }
            points.clear();
        }
        if (pts.length() > 0) {
            try {
                JSONObject body = new JSONObject().put("trip", trip).put("points", pts);
                queue(this, body.toString());
            } catch (Exception ignored) {
                // ne peut pas arriver avec des nombres
            }
        }
        sendPending(this);
    }

    private static synchronized void queue(Context ctx, String json) {
        SharedPreferences p = ctx.getSharedPreferences(Sender.PREFS, Context.MODE_PRIVATE);
        String pending = p.getString("pending", "");
        p.edit().putString("pending", pending.isEmpty() ? json : pending + "\n" + json).apply();
    }

    private static synchronized void sendPending(Context ctx) {
        SharedPreferences p = ctx.getSharedPreferences(Sender.PREFS, Context.MODE_PRIVATE);
        String pending = p.getString("pending", "");
        if (pending.isEmpty()) {
            return;
        }
        StringBuilder left = new StringBuilder();
        for (String json : pending.split("\n")) {
            if (!post(p.getString("server", Sender.DEFAULT_SERVER) + "/api/track", json)) {
                left.append(left.length() > 0 ? "\n" : "").append(json);
            }
        }
        p.edit().putString("pending", left.toString()).apply();
    }

    private static boolean post(String url, String json) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(10_000);
            c.setReadTimeout(10_000);
            c.setRequestMethod("POST");
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            try (OutputStream o = c.getOutputStream()) {
                o.write(json.getBytes(StandardCharsets.UTF_8));
            }
            int code = c.getResponseCode();
            c.disconnect();
            return code == 200;
        } catch (Exception e) {
            return false;
        }
    }

    private Notification notification() {
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, Tr.t("Trajet en cours"), NotificationManager.IMPORTANCE_LOW);
            getSystemService(NotificationManager.class).createNotificationChannel(ch);
            b = new Notification.Builder(this, CHANNEL);
        } else {
            b = new Notification.Builder(this);
        }
        return b.setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle(Tr.t("Trajet en cours"))
                .setContentText(Tr.t("Enregistrement du parcours (GPS coupé à l'arrivée)"))
                .setOngoing(true)
                .build();
    }
}
