package fr.ratamuse.garee;

import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

/**
 * Connexion au Bluetooth de la voiture : depart (position + debut du trace).
 * Deconnexion : arrivee (fin du trace + position de stationnement).
 */
public class BtReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        if (!Flavor.PERSONAL) {
            return; // version generique : pas de suivi des trajets
        }
        String action = intent.getAction();
        boolean connected = BluetoothDevice.ACTION_ACL_CONNECTED.equals(action);
        if (!connected && !BluetoothDevice.ACTION_ACL_DISCONNECTED.equals(action)) {
            return;
        }
        BluetoothDevice dev = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
        SharedPreferences prefs = ctx.getSharedPreferences(Sender.PREFS, Context.MODE_PRIVATE);
        if (dev == null || !prefs.getString("device", "").equals(dev.getAddress())) {
            return; // un autre appareil (ecouteurs, montre...) : on ignore
        }
        Context app = ctx.getApplicationContext();
        String trip;
        if (connected) {
            trip = String.valueOf(System.currentTimeMillis() / 1000);
            prefs.edit().putString("trip", trip).apply();
            try {
                TrackService.begin(app, trip); // trace GPS tant que la voiture est connectee
            } catch (Exception e) {
                // demarrage refuse par Android : on aura au moins le depart et l'arrivee
            }
        } else {
            trip = prefs.getString("trip", "");
        }
        PendingResult pending = goAsync(); // garde l'appli eveillee le temps d'obtenir la position et de l'envoyer
        new Thread(() -> {
            try {
                if (!connected) {
                    TrackService.finish(app);
                }
                Sender.send(app, connected ? "start" : "end", trip);
                Notifier.poll(app); // en passant, les notifications en attente
            } finally {
                pending.finish();
            }
        }).start();
    }
}
