package fr.ratamuse.garee;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Ecran principal : la page du serveur (batterie, charge, clim, historique...) en plein ecran. */
public class MainActivity extends Activity {
    private WebView web;
    private String server;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.parseColor("#07090d"));
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#07090d"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // memorise le mode jour / nuit
        s.setUserAgentString(s.getUserAgentString() + " VoitureGaree/1.0"); // la page affiche alors la carte "Appli"
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if ("garee".equals(u.getScheme())) {
                    if ("setup".equals(u.getHost())) {
                        startActivity(new Intent(MainActivity.this, SetupActivity.class));
                    } else {
                        load(); // garee://retry
                    }
                    return true;
                }
                if (!u.toString().startsWith(server)) { // itineraire Google Maps, liens externes...
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                    return true;
                }
                return false;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    view.loadDataWithBaseURL(null, offlinePage(), "text/html", "utf-8", null);
                }
            }
        });
        setContentView(web);
        load();
    }

    @Override
    protected void onResume() {
        super.onResume();
        SharedPreferences p = getSharedPreferences(Sender.PREFS, MODE_PRIVATE);
        Notifier.schedule(this); // verification periodique des notifications du serveur (secours)
        PushService.start(this); // connexion permanente : notifications en quelques secondes
        Context app = getApplicationContext();
        new Thread(() -> Notifier.poll(app)).start();
        if (Flavor.PERSONAL ? !p.contains("device") : p.getString("server", "").isEmpty()) {
            // premier lancement : adresse du serveur (et, version perso, voiture et autorisations)
            startActivity(new Intent(this, SetupActivity.class));
        } else if (!p.getString("server", Sender.DEFAULT_SERVER).equals(server)) {
            load(); // adresse du serveur modifiee dans les reglages
        } else {
            web.evaluateJavascript("typeof refresh==='function'&&refresh()", null); // donnees a jour au retour
        }
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack(); // Historique / Reglages -> accueil
        } else {
            super.onBackPressed();
        }
    }

    private void load() {
        server = getSharedPreferences(Sender.PREFS, MODE_PRIVATE).getString("server", Sender.DEFAULT_SERVER);
        if (!server.isEmpty()) {
            web.loadUrl(server + "/");
        }
    }

    private String offlinePage() {
        return "<html><body style='background:#07090d;color:#f2f4f8;font-family:sans-serif;padding:32px;text-align:center'>"
                + "<h2>" + Tr.t("Serveur injoignable") + "</h2><p style='color:#8a93a3'>"
                + Tr.t("Vérifie que Tailscale est actif sur le téléphone et que le serveur est allumé.") + "<br><br>" + server + "</p>"
                + "<p><a href='garee://retry' style='display:inline-block;padding:14px 28px;border-radius:14px;"
                + "background:#2fd3ff;color:#000;text-decoration:none;font-weight:bold'>" + Tr.t("Réessayer") + "</a></p>"
                + "<p><a href='garee://setup' style='color:#2fd3ff'>" + Tr.t("Réglages de l’appli") + "</a></p></body></html>";
    }
}
