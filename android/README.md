# EV Companion (appli Android / Android app)

*[English below](#english).*

Petite appli Android compagnon de stellantis-ev-companion : sans publicité, sans compte, sans dépendance.

- Elle affiche la page de ton serveur en plein écran.
- Elle reçoit ses **notifications** en quelques secondes, sans appli tierce. Elle garde une connexion permanente au
  serveur (`GET /api/notifs/wait`), signalée par une notification discrète « EV Companion connecté ».
- Interface en français, anglais, espagnol, italien et allemand, selon la langue du téléphone.

## Installation

1. Télécharge `ev-companion.apk` depuis les *Releases* du dépôt, ouvre-le sur le téléphone et autorise
   l'installation depuis le navigateur ou le gestionnaire de fichiers.
2. Au premier lancement, indique l'adresse de ton serveur (par exemple `http://100.x.y.z:8080` avec Tailscale), puis
   **Enregistrer**.
3. **Autoriser les notifications**, puis **Ne pas optimiser la batterie** : sinon Android coupe la connexion
   permanente et les notifications arrivent en retard.
4. **Tester la connexion**. Ensuite, dans la page : ⚙️ Réglages → *Envoyer une notification de test*.

Les réglages de l'appli restent accessibles depuis la page : ⚙️ Réglages → *Appli Android*.

## Fabriquer l'APK

Sans Android Studio ni Gradle : un JDK 17 et le SDK Android (`build-tools;34.0.0`, `platforms;android-34`) suffisent.

```bash
TOOLS=~/android-build bash build.sh   # TOOLS contient jdk/ et sdk/
```

Au premier lancement, `build.sh` crée une clé de signature (`garee.keystore`, ignorée par git). Garde-la : elle est
nécessaire pour installer une mise à jour par-dessus l'appli existante.

Le code contient aussi un suivi des trajets par Bluetooth et GPS, utilisé seulement par la version personnelle de
l'auteur (dossier `res-perso/`). Il est désactivé dans cette version : les autorisations de localisation et de
Bluetooth déclarées dans le manifeste ne sont jamais demandées.

## English

A small companion Android app for stellantis-ev-companion: no ads, no account, no dependencies.

- It shows your server's page full screen.
- It receives the server's **notifications** within seconds, with no third-party app. It keeps a permanent connection
  to the server (`GET /api/notifs/wait`), shown by a discreet "EV Companion connected" notification.
- Interface in English, French, Spanish, Italian and German, following the phone's language.

### Installation

1. Download `ev-companion.apk` from the repository's *Releases*, open it on the phone and allow installing from your
   browser or file manager.
2. On first launch, enter your server's address (for example `http://100.x.y.z:8080` with Tailscale), then **Save**.
3. **Allow notifications**, then **Don't optimise battery**: otherwise Android cuts the permanent connection and
   notifications arrive late.
4. **Test the connection**. Then, in the page: ⚙️ Réglages → *Envoyer une notification de test* (send a test
   notification).

The app settings remain available from the page: ⚙️ Réglages → *Appli Android*.

### Building the APK

No Android Studio or Gradle needed: a JDK 17 and the Android SDK (`build-tools;34.0.0`, `platforms;android-34`) are
enough.

```bash
TOOLS=~/android-build bash build.sh   # TOOLS contains jdk/ and sdk/
```

On first run, `build.sh` creates a signing key (`garee.keystore`, ignored by git). Keep it: you need it to install an
update over the existing app.

The code also contains trip tracking via Bluetooth and GPS, used only by the author's personal build (`res-perso/`
folder). It is disabled in this version: the location and Bluetooth permissions declared in the manifest are never
requested.

## Licence / License

GPL-3.0-or-later.
