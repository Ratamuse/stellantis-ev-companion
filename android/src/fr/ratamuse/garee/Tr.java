package fr.ratamuse.garee;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Traductions de l'appli (fr, en, es, it, de), selon la langue du telephone. Cle = texte francais. */
final class Tr {
    private static final String[] CODES = {"en", "es", "it", "de"};
    private static final String[][] ROWS = {
            {"Réglages de l’appli", "App settings", "Ajustes de la app", "Impostazioni dell'app", "App-Einstellungen"},
            {"Au départ et à l'arrivée (connexion au Bluetooth de la voiture), la position du téléphone est envoyée à ton "
                    + "serveur, et à personne d'autre. Les notifications du serveur s'affichent ici.",
                    "When you leave and arrive (connection to the car's Bluetooth), the phone's location is sent to your "
                            + "server, and to nobody else. The server's notifications appear here.",
                    "Al salir y al llegar (conexión al Bluetooth del coche), la posición del teléfono se envía a tu servidor, "
                            + "y a nadie más. Las notificaciones del servidor aparecen aquí.",
                    "Alla partenza e all'arrivo (connessione al Bluetooth dell'auto), la posizione del telefono viene inviata "
                            + "al tuo server, e a nessun altro. Le notifiche del server compaiono qui.",
                    "Bei Abfahrt und Ankunft (Verbindung mit dem Bluetooth des Autos) wird der Standort des Telefons an deinen "
                            + "Server gesendet, und an niemanden sonst. Die Benachrichtigungen des Servers erscheinen hier."},
            {"Adresse du serveur", "Server address", "Dirección del servidor", "Indirizzo del server", "Serveradresse"},
            {"Bluetooth de la voiture", "Car Bluetooth", "Bluetooth del coche", "Bluetooth dell'auto", "Bluetooth des Autos"},
            {"Enregistrer", "Save", "Guardar", "Salva", "Speichern"},
            {"Enregistré", "Saved", "Guardado", "Salvato", "Gespeichert"},
            {"Autorisations", "Permissions", "Permisos", "Autorizzazioni", "Berechtigungen"},
            {"1. Bluetooth, localisation et notifications", "1. Bluetooth, location and notifications",
                    "1. Bluetooth, ubicación y notificaciones", "1. Bluetooth, posizione e notifiche",
                    "1. Bluetooth, Standort und Benachrichtigungen"},
            {"2. Localisation : « Toujours autoriser »", "2. Location: “Allow all the time”", "2. Ubicación: «Permitir siempre»",
                    "2. Posizione: «Consenti sempre»", "2. Standort: „Immer zulassen“"},
            {"3. Ne pas optimiser la batterie", "3. Don't optimise battery", "3. No optimizar la batería",
                    "3. Non ottimizzare la batteria", "3. Akku nicht optimieren"},
            {"Test", "Test", "Prueba", "Prova", "Test"},
            {"Envoyer ma position maintenant", "Send my location now", "Enviar mi posición ahora", "Invia ora la mia posizione",
                    "Meinen Standort jetzt senden"},
            {"Tailscale doit rester actif sur le téléphone (VPN permanent).", "Tailscale must stay on on the phone (always-on VPN).",
                    "Tailscale debe permanecer activo en el teléfono (VPN permanente).",
                    "Tailscale deve restare attivo sul telefono (VPN sempre attiva).",
                    "Tailscale muss auf dem Telefon aktiv bleiben (dauerhaftes VPN)."},
            {"(fais d'abord l'étape 1, Bluetooth allumé)", "(do step 1 first, with Bluetooth on)",
                    "(haz primero el paso 1, con el Bluetooth encendido)", "(fai prima il passo 1, con il Bluetooth acceso)",
                    "(zuerst Schritt 1, Bluetooth eingeschaltet)"},
            {"Fais d'abord l'étape 1", "Do step 1 first", "Haz primero el paso 1", "Fai prima il passo 1", "Zuerst Schritt 1"},
            {"Envoi en cours…", "Sending…", "Enviando…", "Invio in corso…", "Wird gesendet…"},
            {"Voiture : ", "Car: ", "Coche: ", "Auto: ", "Auto: "},
            {"pas encore choisie", "not chosen yet", "aún no elegido", "non ancora scelta", "noch nicht gewählt"},
            {"Localisation : ", "Location: ", "Ubicación: ", "Posizione: ", "Standort: "},
            {"en arrière-plan : ", "in background: ", "en segundo plano: ", "in background: ", "im Hintergrund: "},
            {"oui", "yes", "sí", "sì", "ja"},
            {"NON", "NO", "NO", "NO", "NEIN"},
            {"Dernier envoi : ", "Last sent: ", "Último envío: ", "Ultimo invio: ", "Zuletzt gesendet: "},
            {"aucun", "none", "ninguno", "nessuno", "keiner"},
            {"position indisponible (GPS coupé ?)", "location unavailable (GPS off?)", "posición no disponible (¿GPS apagado?)",
                    "posizione non disponibile (GPS spento?)", "Standort nicht verfügbar (GPS aus?)"},
            {"envoyé (précision %d m)", "sent (accuracy %d m)", "enviado (precisión %d m)", "inviato (precisione %d m)",
                    "gesendet (Genauigkeit %d m)"},
            {"refusé par le serveur (%d)", "rejected by the server (%d)", "rechazado por el servidor (%d)",
                    "rifiutato dal server (%d)", "vom Server abgelehnt (%d)"},
            {"localisation non autorisée", "location not allowed", "ubicación no autorizada", "posizione non autorizzata",
                    "Standort nicht erlaubt"},
            {"échec : serveur injoignable (Tailscale actif ?)", "failed: server unreachable (Tailscale on?)",
                    "fallo: servidor inaccesible (¿Tailscale activo?)", "errore: server irraggiungibile (Tailscale attivo?)",
                    "Fehler: Server nicht erreichbar (Tailscale aktiv?)"},
            {"départ", "departure", "salida", "partenza", "Abfahrt"},
            {"arrivée", "arrival", "llegada", "arrivo", "Ankunft"},
            {"Serveur injoignable", "Server unreachable", "Servidor inaccesible", "Server irraggiungibile", "Server nicht erreichbar"},
            {"Vérifie que Tailscale est actif sur le téléphone et que le serveur est allumé.",
                    "Check that Tailscale is on on the phone and that the server is running.",
                    "Comprueba que Tailscale está activo en el teléfono y que el servidor está encendido.",
                    "Controlla che Tailscale sia attivo sul telefono e che il server sia acceso.",
                    "Prüfe, ob Tailscale auf dem Telefon aktiv ist und der Server läuft."},
            {"Réessayer", "Retry", "Reintentar", "Riprova", "Erneut versuchen"},
            {"Alertes", "Alerts", "Alertas", "Avvisi", "Warnungen"},
            {"Informations", "Information", "Información", "Informazioni", "Informationen"},
            {"Connexion au serveur", "Server connection", "Conexión al servidor", "Connessione al server", "Serververbindung"},
            {"%s connecté", "%s connected", "%s conectado", "%s connesso", "%s verbunden"},
            {"L'appli affiche la page de ton serveur stellantis-ev-companion et ses notifications. Indique son adresse, "
                    + "par exemple http://100.x.y.z:8080 avec Tailscale.",
                    "The app shows your stellantis-ev-companion server page and its notifications. Enter its address, "
                            + "for example http://100.x.y.z:8080 with Tailscale.",
                    "La app muestra la página de tu servidor stellantis-ev-companion y sus notificaciones. Indica su "
                            + "dirección, por ejemplo http://100.x.y.z:8080 con Tailscale.",
                    "L'app mostra la pagina del tuo server stellantis-ev-companion e le sue notifiche. Indica il suo "
                            + "indirizzo, per esempio http://100.x.y.z:8080 con Tailscale.",
                    "Die App zeigt die Seite deines stellantis-ev-companion-Servers und seine Benachrichtigungen. Gib "
                            + "seine Adresse ein, zum Beispiel http://100.x.y.z:8080 mit Tailscale."},
            {"Autoriser les notifications", "Allow notifications", "Permitir notificaciones", "Consenti le notifiche",
                    "Benachrichtigungen erlauben"},
            {"Ne pas optimiser la batterie", "Don't optimise battery", "No optimizar la batería", "Non ottimizzare la batteria",
                    "Akku nicht optimieren"},
            {"Masquer la notification permanente", "Hide the permanent notification", "Ocultar la notificación permanente",
                    "Nascondi la notifica permanente", "Dauerhafte Benachrichtigung ausblenden"},
            {"Désactive l'interrupteur de cette catégorie : la connexion continue et les alertes arrivent toujours.",
                    "Turn off this category's switch: the connection keeps running and alerts still arrive.",
                    "Desactiva el interruptor de esta categoría: la conexión sigue activa y las alertas siguen llegando.",
                    "Disattiva l'interruttore di questa categoria: la connessione continua e gli avvisi arrivano comunque.",
                    "Schalte diese Kategorie aus: Die Verbindung läuft weiter und Warnungen kommen weiterhin an."},
            {"Tester la connexion", "Test the connection", "Probar la conexión", "Prova la connessione", "Verbindung testen"},
            {"Connexion au serveur réussie ✔", "Connected to the server ✔", "Conexión con el servidor correcta ✔",
                    "Connessione al server riuscita ✔", "Verbindung zum Server erfolgreich ✔"},
            {"Serveur injoignable : vérifie l'adresse et Tailscale.", "Server unreachable: check the address and Tailscale.",
                    "Servidor inaccesible: comprueba la dirección y Tailscale.",
                    "Server irraggiungibile: controlla l'indirizzo e Tailscale.",
                    "Server nicht erreichbar: Adresse und Tailscale prüfen."},
            {"Notifications : ", "Notifications: ", "Notificaciones: ", "Notifiche: ", "Benachrichtigungen: "},
            {"Dernier test : ", "Last test: ", "Última prueba: ", "Ultimo test: ", "Letzter Test: "},
            {"Réception des notifications en direct", "Receiving live notifications", "Recibiendo notificaciones en directo",
                    "Ricezione delle notifiche in diretta", "Benachrichtigungen werden live empfangen"},
            {"Trajet en cours", "Trip in progress", "Trayecto en curso", "Tragitto in corso", "Fahrt läuft"},
            {"Enregistrement du parcours (GPS coupé à l'arrivée)", "Recording the route (GPS off on arrival)",
                    "Grabando el recorrido (GPS apagado al llegar)", "Registrazione del percorso (GPS spento all'arrivo)",
                    "Strecke wird aufgezeichnet (GPS aus bei Ankunft)"},
    };
    private static final Map<String, String[]> MAP = new HashMap<>();

    static {
        for (String[] row : ROWS) {
            MAP.put(row[0], row);
        }
    }

    private Tr() {
    }

    static String t(String fr) {
        String lang = Locale.getDefault().getLanguage();
        String[] row = MAP.get(fr);
        if (row == null) {
            return fr;
        }
        for (int i = 0; i < CODES.length; i++) {
            if (CODES[i].equals(lang)) {
                return row[i + 1];
            }
        }
        return "fr".equals(lang) ? fr : row[1]; // autre langue : anglais
    }
}
