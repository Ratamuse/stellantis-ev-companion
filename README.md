# stellantis-ev-companion

Page web compagnon de [psa_car_controller](https://github.com/flobz/psa_car_controller) pour les voitures électriques
du groupe Stellantis (Peugeot, Citroën, DS, Opel, Vauxhall…), pensée pour le téléphone.

*English version below.*

<table>
  <tr>
    <td align="center"><img src="docs/accueil-sombre.png" width="220" alt="Accueil, mode sombre, voiture en charge"><br><sub>Accueil (mode sombre, en charge)</sub></td>
    <td align="center"><img src="docs/accueil-jour.png" width="220" alt="Accueil, mode jour"><br><sub>Accueil (mode jour)</sub></td>
    <td align="center"><img src="docs/historique.png" width="220" alt="Historique : distance, consommation, coût, graphique par mois"><br><sub>Historique</sub></td>
    <td align="center"><img src="docs/reglages.png" width="220" alt="Réglages : nom de la voiture, notifications, préchauffage météo"><br><sub>Réglages</sub></td>
  </tr>
</table>

<sub>Captures réalisées avec des données fictives.</sub>

## Ce que ça fait

- **Arrêt de charge fiable à X %** (et/ou à une heure donnée). L'arrêt intégré à psa_car_controller ne se déclenche
  pas quand l'état de charge manque dans son cache (voir [Pourquoi ce projet](#pourquoi-ce-projet)) : cette page
  interroge directement l'API et arrête la charge elle-même.
- **Heures creuses automatiques** : l'heure de début de charge différée est recalée sur la prochaine plage creuse
  (plusieurs plages possibles), la charge est suspendue en fin de plage et reprend à la suivante. Une charge qui
  démarre en heures pleines est remise en attente.
- **Clim / chauffage** : démarrage immédiat, programmation par jours de la semaine, et **préconditionnement selon la
  météo** (Open-Meteo) : il n'est lancé avant un départ que s'il fait froid ou chaud.
- **Historique** : trajets, consommation, charges et **coût** (tarifs heures pleines / creuses de psa_car_controller),
  graphique par mois, compteur kilométrique.
- **Autonomie « à ton rythme »** : estimée à partir de la consommation réelle des derniers trajets, corrigée par la
  température.
- **Notifications** sur le téléphone avec [ntfy](https://ntfy.sh) : oubli de branchement, fin de charge, charge
  interrompue, charge en heures pleines, préchauffage, bilan mensuel.
- Mode **jour / nuit**, interface en français.

## Prérequis

- psa_car_controller qui fonctionne (Docker ou pip), avec les commandes à distance activées (code SMS + PIN).
- Python 3.9 ou plus récent. **Aucune dépendance** : uniquement la bibliothèque standard.
- Recommandé : [Tailscale](https://tailscale.com) pour accéder à la page depuis le téléphone.

## Installation (Raspberry Pi / Linux)

```bash
sudo mkdir -p /opt/stellantis-ev-companion
sudo cp app.py config.example.json /opt/stellantis-ev-companion/
cd /opt/stellantis-ev-companion
sudo cp config.example.json config.json
sudo nano config.json            # VIN, heures creuses, départs...
sudo cp deploy/stellantis-ev-companion.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now stellantis-ev-companion
```

La page est alors sur `http://<adresse-du-serveur>:8080`. Dans **⚙️ Réglages**, abonne-toi au sujet ntfy affiché
dans l'appli ntfy, puis active les fonctions voulues.

Photo facultative : dépose `car.png` (ou `.webp`, `.jpg`, fond transparent) à côté de `app.py`. Sans photo, une
silhouette neutre est affichée. N'utilise pas d'images protégées si tu publies ton installation.

## Accès depuis le téléphone, sans ouvrir de port : Tailscale

La page pilote la voiture et n'a pas de mot de passe : elle ne doit **jamais** être accessible depuis Internet
(pas de redirection de port sur la box). [Tailscale](https://tailscale.com) crée un réseau privé chiffré entre tes
appareils : le téléphone voit le serveur comme s'il était à la maison, où que tu sois.

1. Crée un compte sur tailscale.com (connexion Google, Microsoft, Apple ou GitHub) et **active la double
   authentification** sur ce compte : c'est elle qui protège l'accès.
2. Sur le serveur :
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
   Ouvre le lien affiché et connecte-toi avec le même compte.
3. Dans la console Tailscale (*Machines*), menu « … » du serveur → **Disable key expiry**, sinon il se déconnecte au
   bout de 180 jours.
4. Sur le téléphone, installe l'appli **Tailscale**, connecte-toi avec le même compte et active-la.
5. Ouvre `http://<nom-du-serveur>:8080` (ou `http://100.x.y.z:8080`, adresse donnée par `tailscale ip -4`) et
   ajoute la page à l'écran d'accueil.

Bonus : avec Tailscale, tu peux aussi te connecter en SSH au serveur depuis n'importe où et fermer tout port ouvert
sur ta box.

## Notifications sur le téléphone : ntfy

La page envoie ses notifications avec [ntfy](https://ntfy.sh), une appli gratuite (Android et iPhone) qui ne demande
pas de compte.

1. Installe l'appli **ntfy** sur le téléphone.
2. Dans la page, ouvre **⚙️ Réglages** : la carte *Notifications* affiche ton **sujet**, tiré au hasard au premier
   lancement (par exemple `ev-8a98a85fba109e95`).
3. Dans ntfy, appuie sur **+**, colle ce sujet, garde le serveur `ntfy.sh` et valide.
4. Appuie sur **Envoyer une notification de test** dans la page : elle doit arriver en quelques secondes.
5. Choisis les alertes voulues (oubli de branchement, fin de charge, charge en heures pleines…).

Les messages passent par le service public ntfy.sh : quiconque connaît le sujet peut les lire. Ils ne contiennent ni
position ni identifiants, seulement niveaux de batterie, coûts et températures. Ne partage pas ton sujet. Pour un
contrôle total, tu peux héberger ton propre serveur ntfy et changer `NTFY_SERVER` dans `app.py`.

## Réglages (`config.json`)

| Clé | Rôle | Exemple |
|---|---|---|
| `vin` | VIN de la voiture (obligatoire) | `"VR3XXXXXXXXXXXXXX"` |
| `psacc_url` | Adresse de psa_car_controller | `"http://127.0.0.1:5000"` |
| `port` | Port de la page | `8080` |
| `brand`, `model` | Nom affiché (modifiable aussi dans Réglages) | `"Peugeot"`, `"e-208"` |
| `battery_kwh` | Capacité utile de la batterie | `46` |
| `offpeak` | Plages d'heures creuses `[début, fin]` | `[["22:00", "06:00"]]` |
| `departures` | Départs habituels pour le préconditionnement : jours (0 = lundi), heure, lieu | voir l'exemple |
| `weather` | Lieu de référence pour la température (sinon le premier départ) | `{"place": "Lyon", "lat": 45.76, "lon": 4.84}` |
| `commute` | Trajet type affiché avec l'autonomie (facultatif) | `{"label": "Maison ↔ Travail", "km": 25}` |

Les réglages faits dans la page (limites, notifications, programmations…) sont enregistrés dans le dossier
d'état (`StateDirectory` du service systemd, sinon à côté de `app.py`).

## Pourquoi ce projet

Sur au moins une Peugeot e-208 (2021), le journal de psa_car_controller affiche en continu
`charging status not available from api` : l'état de charge n'est pas présent dans les données en cache, alors qu'une
requête fraîche (`/get_vehicleinfo/<vin>?from_cache=0`) le renvoie bien. Conséquence : le contrôle de charge
(`percentage_threshold`, `stop_hour`) ne voit jamais la voiture « en charge » et **ne l'arrête pas** ; l'historique des
charges n'a pas de fin ni de coût.

Cette page contourne le problème :
- elle interroge l'API avec `from_cache=0` toutes les 5 minutes (2 minutes pendant une charge) ;
- pour arrêter une charge, elle programme la charge différée à une heure **déjà passée** (`/charge_hour`) :
  la voiture se met en attente jusqu'au lendemain (même technique que le « postpone » de psa_car_controller) ;
- elle enregistre elle-même début, fin, pourcentages et coût de chaque charge.

Autres constats : sur ce véhicule, la voiture repasse en **charge immédiate à chaque branchement** ; renvoyer la
commande de charge différée une fois branchée la remet bien en attente (LED bleue). La position GPS n'est pas
fournie par l'API utilisée (coordonnées nulles), alors que l'appli officielle l'affiche.

## Sécurité

- **N'expose jamais la page ni psa_car_controller sur Internet** : elles n'ont pas de mot de passe et pilotent la
  voiture. Utilise Tailscale (ou un VPN) ; ne redirige aucun port sur ta box.
- Le sujet ntfy est tiré au hasard ; quiconque le connaît peut lire les notifications (pas de position ni
  d'identifiants dedans).

## Limites

- Testé sur une Peugeot e-208 (2021) ; les autres modèles Stellantis compatibles avec psa_car_controller devraient
  fonctionner, sans garantie.
- Interface en français uniquement.
- Projet personnel, sans lien avec Stellantis. Les noms de marques appartiennent à leurs propriétaires.

## Licence

GPL-3.0-or-later, comme psa_car_controller.

---

## English

A phone-friendly companion web page for [psa_car_controller](https://github.com/flobz/psa_car_controller), for
Stellantis electric cars (Peugeot, Citroën, DS, Opel, Vauxhall…). The UI is in French (screenshots at the top of
this page, made with fictional data).

**Features:** reliable charge stop at a percentage and/or time (works around psa_car_controller's charge control not
firing when the cached status lacks the charging state), automatic off-peak charging windows (several windows,
suspend at window end, re-defer when a charge starts in peak hours), climate control with weekday schedule and
**weather-based preconditioning** (Open-Meteo), trip / consumption / charge-cost history, "at your pace" range
estimate, [ntfy](https://ntfy.sh) push notifications, day/night theme.

**Requirements:** a working psa_car_controller with remote commands enabled; Python ≥ 3.9 (standard library only);
Tailscale or a VPN recommended — never expose the page or psa_car_controller to the Internet.

**Install:** copy `app.py` and `config.example.json` → `config.json` (set your VIN, off-peak windows, departures),
install `deploy/stellantis-ev-companion.service`, enable it, open `http://<server>:8080`.

**Phone access:** install [Tailscale](https://tailscale.com) on the server (`curl -fsSL https://tailscale.com/install.sh | sh`
then `sudo tailscale up`) and on your phone with the same account (enable 2FA on it, disable key expiry for the
server), then open `http://<server-name>:8080`. Do not forward any port on your router.

**Notifications:** install the [ntfy](https://ntfy.sh) app, subscribe to the random topic shown in ⚙️ Réglages, and
press the test button. Messages go through the public ntfy.sh server; keep the topic private.

**Why:** on a 2021 e-208, psa_car_controller constantly logs `charging status not available from api`; its charge
control therefore never sees the car charging and never stops it. This page polls the API with `from_cache=0` and
stops the charge itself by setting the delayed-charge hour to a time already passed (`/charge_hour`), which makes the
car wait until the next day. See the French section above for details.

License: GPL-3.0-or-later. Not affiliated with Stellantis.
