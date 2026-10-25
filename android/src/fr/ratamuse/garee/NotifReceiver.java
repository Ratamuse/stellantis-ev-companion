package fr.ratamuse.garee;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Reveil periodique (et demarrage du telephone / mise a jour de l'appli) : verifie les notifications du serveur. */
public class NotifReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        Context app = ctx.getApplicationContext();
        PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                PushService.start(app); // relance la connexion permanente si Android l'a arretee
                Notifier.poll(app);
            } finally {
                Notifier.schedule(app); // la verification suivante
                pending.finish();
            }
        }).start();
    }
}
