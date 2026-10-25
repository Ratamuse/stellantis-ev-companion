package fr.ratamuse.garee;

import android.content.Context;
import android.content.SharedPreferences;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.HandlerThread;

import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/** Obtient la position du telephone et l'envoie au serveur : GET <serveur>/api/park?lat=..&lon=..&acc=.. */
final class Sender {
    static final String PREFS = "garee";
    static final String DEFAULT_SERVER = Flavor.DEFAULT_SERVER; // vide dans la version generique

    private Sender() {
    }

    /** kind : start (depart), end (arrivee), test ; trip : identifiant du trajet (vide pour un test). */
    static void send(Context ctx, String kind, String trip) {
        SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String result;
        try {
            Location loc = locate(ctx);
            if (loc == null) {
                result = Tr.t("position indisponible (GPS coupé ?)");
            } else {
                String url = p.getString("server", DEFAULT_SERVER) + "/api/park?lat=" + loc.getLatitude()
                        + "&lon=" + loc.getLongitude() + "&acc=" + Math.round(loc.getAccuracy()) + "&kind=" + kind + "&trip=" + trip;
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(10000);
                c.setReadTimeout(10000);
                int code = c.getResponseCode();
                c.disconnect();
                result = code == 200 ? String.format(Tr.t("envoyé (précision %d m)"), Math.round(loc.getAccuracy()))
                        : String.format(Tr.t("refusé par le serveur (%d)"), code);
            }
        } catch (SecurityException e) {
            result = Tr.t("localisation non autorisée");
        } catch (Exception e) {
            result = Tr.t("échec : serveur injoignable (Tailscale actif ?)");
        }
        String when = new SimpleDateFormat("dd/MM HH:mm", Locale.FRANCE).format(new Date());
        String label = "start".equals(kind) ? Tr.t("départ") : "end".equals(kind) ? Tr.t("arrivée") : kind;
        p.edit().putString("last", when + " (" + label + ") : " + result).apply();
    }

    /** Position recente deja connue si elle est fraiche et precise, sinon une nouvelle mesure (GPS puis reseau). */
    private static Location locate(Context ctx) throws InterruptedException {
        LocationManager lm = ctx.getSystemService(LocationManager.class);
        Location best = null;
        for (String prov : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER,
                LocationManager.PASSIVE_PROVIDER}) {
            Location l = lm.getLastKnownLocation(prov);
            if (l != null && (best == null || l.getTime() > best.getTime())) {
                best = l;
            }
        }
        if (best != null && System.currentTimeMillis() - best.getTime() < 120_000 && best.getAccuracy() <= 50) {
            return best;
        }
        Location now = current(lm, LocationManager.GPS_PROVIDER, 25);
        if (now == null) {
            now = current(lm, LocationManager.NETWORK_PROVIDER, 10);
        }
        return now != null ? now : best;
    }

    @SuppressWarnings("deprecation")
    private static Location current(LocationManager lm, String prov, int seconds) throws InterruptedException {
        if (!lm.isProviderEnabled(prov)) {
            return null;
        }
        final Location[] out = new Location[1];
        CountDownLatch done = new CountDownLatch(1);
        if (Build.VERSION.SDK_INT >= 30) {
            lm.getCurrentLocation(prov, null, Executors.newSingleThreadExecutor(), l -> {
                out[0] = l;
                done.countDown();
            });
        } else {
            HandlerThread t = new HandlerThread("position");
            t.start();
            lm.requestSingleUpdate(prov, new LocationListener() {
                @Override
                public void onLocationChanged(Location l) {
                    out[0] = l;
                    done.countDown();
                    t.quitSafely();
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
            }, t.getLooper());
        }
        done.await(seconds, TimeUnit.SECONDS);
        return out[0];
    }
}
