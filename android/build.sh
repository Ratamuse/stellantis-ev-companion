#!/usr/bin/env bash
# Fabrique l'APK sans Android Studio ni Gradle : aapt2 -> javac -> d8 -> zipalign -> apksigner.
# Outils attendus (installes une fois) : un JDK 17 et le SDK Android (build-tools 34.0.0, platforms;android-34).
#
# Deux versions depuis le meme code :
#  - generique "EV Companion" (ev-companion.apk) : page du serveur + notifications ;
#  - personnelle "e-208" (e-208.apk) si le dossier res-perso existe : icone avec la photo de ta voiture, suivi des
#    trajets par Bluetooth/GPS, adresse du serveur par defaut lue dans server.txt.
# GENERIC=1 ./build.sh force la version generique.
set -euo pipefail
cd "$(dirname "$0")"

TOOLS="${TOOLS:-$HOME/android-build}"
JDK="${JDK:-$TOOLS/jdk}"
SDK="${SDK:-$TOOLS/sdk}"
BT="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
JAVA="$JDK/bin/java"

if [ -d res-perso ] && [ "${GENERIC:-0}" != 1 ]; then
    RES=res-perso PERSONAL=true NAME="e-208" PKG=fr.ratamuse.garee OUT=e-208.apk
    SERVER="$(tr -d '\r\n' < server.txt 2>/dev/null || true)"
else
    RES=res PERSONAL=false NAME="EV Companion" PKG=fr.ratamuse.evcompanion OUT=ev-companion.apk SERVER=""
fi

rm -rf build
mkdir -p build/classes build/gen/fr/ratamuse/garee
cat > build/gen/fr/ratamuse/garee/Flavor.java <<EOF
package fr.ratamuse.garee;

/** Genere par build.sh : version de l'appli. */
final class Flavor {
    static final boolean PERSONAL = $PERSONAL;
    static final String DEFAULT_SERVER = "$SERVER";

    private Flavor() {
    }
}
EOF
sed "s/android:label=\"e-208\"/android:label=\"$NAME\"/" AndroidManifest.xml > build/AndroidManifest.xml

echo "1/5 manifeste et icones ($NAME)"
"$BT/aapt2" compile --dir "$RES" -o build/res.zip
"$BT/aapt2" link -o build/base.apk --manifest build/AndroidManifest.xml -I "$ANDROID_JAR" \
    --rename-manifest-package "$PKG" --min-sdk-version 26 --target-sdk-version 34 build/res.zip

echo "2/5 compilation Java"
"$JDK/bin/javac" -nowarn -encoding UTF-8 -source 8 -target 8 -bootclasspath "$ANDROID_JAR" \
    -classpath "$BT/core-lambda-stubs.jar" \
    -d build/classes $(find src build/gen -name '*.java') 2>&1 | grep -v "^warning\|^Note\|^[0-9]* warning" || true
test -f build/classes/fr/ratamuse/garee/MainActivity.class

echo "3/5 conversion pour Android (d8)"
"$JAVA" -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 --release --min-api 26 --lib "$ANDROID_JAR" \
    --output build $(find build/classes -name '*.class')

echo "4/5 assemblage"
cp build/base.apk build/unsigned.apk
(cd build && "$JDK/bin/jar" -u -M -f unsigned.apk classes.dex)
"$BT/zipalign" -f 4 build/unsigned.apk build/aligned.apk

echo "5/5 signature"
if [ ! -f garee.keystore ]; then  # cle personnelle, creee une seule fois, jamais publiee
    head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' > keystore-pass.txt
    "$JDK/bin/keytool" -genkeypair -keystore garee.keystore -alias garee -keyalg RSA -keysize 2048 \
        -validity 10000 -storepass "$(cat keystore-pass.txt)" -dname "CN=Voiture garee" >/dev/null
fi
"$JAVA" -jar "$BT/lib/apksigner.jar" sign --ks garee.keystore --ks-pass "pass:$(cat keystore-pass.txt)" \
    --out "$OUT" build/aligned.apk
"$JAVA" -jar "$BT/lib/apksigner.jar" verify "$OUT"
echo "OK : $(pwd)/$OUT ($(du -k "$OUT" | cut -f1) Ko)"
