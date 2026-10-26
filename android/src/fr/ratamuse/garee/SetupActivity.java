package fr.ratamuse.garee;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

/** Reglages de l'appli : serveur, Bluetooth de la voiture, autorisations, test. */
public class SetupActivity extends Activity {
    private SharedPreferences prefs;
    private EditText server;
    private Spinner devices;
    private TextView status;
    private final List<String> addresses = new ArrayList<>();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences(Sender.PREFS, MODE_PRIVATE);
        int pad = dp(16);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(pad, pad, pad, pad);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(col);
        setContentView(scroll);

        TextView title = text(Tr.t("Réglages de l’appli"));
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        col.addView(title);
        col.addView(text(Flavor.PERSONAL
                ? Tr.t("Au départ et à l'arrivée (connexion au Bluetooth de la voiture), la position du téléphone "
                + "est envoyée à ton serveur, et à personne d'autre. Les notifications du serveur s'affichent ici.")
                : Tr.t("L'appli affiche la page de ton serveur stellantis-ev-companion et ses notifications. Indique son adresse, "
                + "par exemple http://100.x.y.z:8080 avec Tailscale.")));

        col.addView(heading(Tr.t("Adresse du serveur")));
        server = new EditText(this);
        server.setSingleLine();
        server.setText(prefs.getString("server", Sender.DEFAULT_SERVER));
        server.setHint("http://100.x.y.z:8080");
        col.addView(server);

        devices = new Spinner(this);
        if (Flavor.PERSONAL) {
            col.addView(heading(Tr.t("Bluetooth de la voiture")));
            col.addView(devices);
        }
        col.addView(button(Tr.t("Enregistrer"), v -> save()));

        if (!Flavor.PERSONAL) { // version generique : notifications seulement, pas de suivi des trajets
            col.addView(heading(Tr.t("Autorisations")));
            col.addView(button(Tr.t("Autoriser les notifications"), v -> askPermissions()));
            col.addView(button(Tr.t("Ne pas optimiser la batterie"),
                    v -> startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))));
            col.addView(button(Tr.t("Masquer la notification permanente"), v -> hideServiceNotification()));
            col.addView(text(Tr.t("Désactive l'interrupteur de cette catégorie : la connexion continue et les alertes arrivent toujours.")));
            col.addView(heading(Tr.t("Test")));
            col.addView(button(Tr.t("Tester la connexion"), v -> testServer()));
            status = text("");
            col.addView(status);
            return;
        }

        col.addView(heading(Tr.t("Autorisations")));
        col.addView(button(Tr.t("1. Bluetooth, localisation et notifications"), v -> askPermissions()));
        col.addView(button(Tr.t("2. Localisation : « Toujours autoriser »"), v -> askBackground()));
        col.addView(button(Tr.t("3. Ne pas optimiser la batterie"),
                v -> startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))));
        col.addView(button(Tr.t("Masquer la notification permanente"), v -> hideServiceNotification()));
        col.addView(text(Tr.t("Désactive l'interrupteur de cette catégorie : la connexion continue et les alertes arrivent toujours.")));

        col.addView(heading(Tr.t("Test")));
        col.addView(button(Tr.t("Envoyer ma position maintenant"), v -> test()));
        status = text("");
        col.addView(status);
        col.addView(text(Tr.t("Tailscale doit rester actif sur le téléphone (VPN permanent).")));
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadDevices();
        refresh();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        loadDevices();
        refresh();
    }

    private void loadDevices() {
        if (!Flavor.PERSONAL) {
            return;
        }
        List<String> names = new ArrayList<>();
        addresses.clear();
        try {
            BluetoothAdapter adapter = getSystemService(BluetoothManager.class).getAdapter();
            if (adapter != null && granted(btPermission())) {
                for (BluetoothDevice d : adapter.getBondedDevices()) {
                    names.add(d.getName() + "  (" + d.getAddress() + ")");
                    addresses.add(d.getAddress());
                }
            }
        } catch (SecurityException ignored) {
            // autorisation Bluetooth pas encore donnee
        }
        if (names.isEmpty()) {
            names.add(Tr.t("(fais d'abord l'étape 1, Bluetooth allumé)"));
        }
        devices.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, names));
        int i = addresses.indexOf(prefs.getString("device", ""));
        if (i >= 0) {
            devices.setSelection(i);
        }
    }

    private void save() {
        SharedPreferences.Editor e = prefs.edit()
                .putString("server", server.getText().toString().trim().replaceAll("/+$", ""));
        int i = devices.getSelectedItemPosition();
        if (i >= 0 && i < addresses.size()) {
            e.putString("device", addresses.get(i)).putString("deviceName", (String) devices.getSelectedItem());
        }
        e.apply();
        Toast.makeText(this, Tr.t("Enregistré"), Toast.LENGTH_SHORT).show();
        refresh();
    }

    private void testServer() {
        save();
        status.setText(Tr.t("Envoi en cours…"));
        new Thread(() -> {
            boolean ok = Notifier.fetch(getApplicationContext(), 0);
            prefs.edit().putString("last", Tr.t(ok ? "Connexion au serveur réussie ✔"
                    : "Serveur injoignable : vérifie l'adresse et Tailscale.")).apply();
            runOnUiThread(this::refresh);
        }).start();
    }

    /** Ouvre le reglage Android de la categorie « Connexion au serveur ». */
    private void hideServiceNotification() {
        PushService.createChannel(this);
        startActivity(new Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName())
                .putExtra(Settings.EXTRA_CHANNEL_ID, PushService.CHANNEL));
    }

    private void askPermissions() {
        if (!Flavor.PERSONAL) {
            if (Build.VERSION.SDK_INT >= 33) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
            }
            return;
        }
        List<String> p = new ArrayList<>();
        p.add(Manifest.permission.ACCESS_FINE_LOCATION);
        p.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        if (Build.VERSION.SDK_INT >= 31) {
            p.add(Manifest.permission.BLUETOOTH_CONNECT);
        }
        if (Build.VERSION.SDK_INT >= 33) {
            p.add(Manifest.permission.POST_NOTIFICATIONS); // notification "Trajet en cours"
        }
        requestPermissions(p.toArray(new String[0]), 1);
    }

    private void askBackground() {
        if (!granted(Manifest.permission.ACCESS_FINE_LOCATION)) {
            Toast.makeText(this, Tr.t("Fais d'abord l'étape 1"), Toast.LENGTH_LONG).show();
            return;
        }
        // Android ouvre alors la page des reglages : choisir « Toujours autoriser »
        requestPermissions(new String[]{Manifest.permission.ACCESS_BACKGROUND_LOCATION}, 2);
    }

    private void test() {
        save();
        status.setText(Tr.t("Envoi en cours…"));
        new Thread(() -> {
            Sender.send(getApplicationContext(), "test", "");
            runOnUiThread(this::refresh);
        }).start();
    }

    private void refresh() {
        if (!Flavor.PERSONAL) {
            boolean notifs = Build.VERSION.SDK_INT < 33 || granted(Manifest.permission.POST_NOTIFICATIONS);
            status.setText(Tr.t("Notifications : ") + (notifs ? Tr.t("oui") : Tr.t("NON"))
                    + "\n" + Tr.t("Dernier test : ") + prefs.getString("last", Tr.t("aucun")));
            return;
        }
        boolean bg = Build.VERSION.SDK_INT < 29 || granted(Manifest.permission.ACCESS_BACKGROUND_LOCATION);
        String yes = Tr.t("oui"), no = Tr.t("NON");
        status.setText(Tr.t("Voiture : ") + prefs.getString("deviceName", Tr.t("pas encore choisie"))
                + "\n" + Tr.t("Localisation : ") + (granted(Manifest.permission.ACCESS_FINE_LOCATION) ? yes : no)
                + "  ·  " + Tr.t("en arrière-plan : ") + (bg ? yes : no)
                + "\n" + Tr.t("Dernier envoi : ") + prefs.getString("last", Tr.t("aucun")));
    }

    private String btPermission() {
        return Build.VERSION.SDK_INT >= 31 ? Manifest.permission.BLUETOOTH_CONNECT : Manifest.permission.BLUETOOTH;
    }

    private boolean granted(String perm) {
        return checkSelfPermission(perm) == PackageManager.PERMISSION_GRANTED;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private TextView text(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(15);
        t.setPadding(0, dp(4), 0, dp(4));
        return t;
    }

    private TextView heading(String s) {
        TextView t = text(s);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(18), 0, dp(2));
        return t;
    }

    private Button button(String label, View.OnClickListener action) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setOnClickListener(action);
        return b;
    }
}
