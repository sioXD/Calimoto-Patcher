# Calimoto App Modifikationen - Patch-Dokumentation

**Dokumentation für:** Calimoto App Premium-Feature Deaktivierung
**Version:** 2.0
**Datum:** 2026-04-08
**Ziel:** Navigation & Profil-Banner von Premium-Checks befreien + GPX Export

---

## 📋 Überblick

Diese Dokumentation beschreibt, wie Premium-Prompts und Upgrade-Banner aus der Calimoto App entfernt werden. Die Änderungen sind strukturiert,um auf zukünftige App-Versionen übertragen zu werden.

### Modifizierte Features:
- ✅ Navigation lädt ohne Premium-Sperre für alle Konten
- ❌ Profil-Seite zeigt kein Upgrade-Banner
- ✅ Trial-Timeline wird nicht angezeigt
- ✅ **NEU:** GPX Export funktioniert ohne Premium-Paywall

---

## 🔧 Änderungen nach Kategorie

### **NEU: 0. GPX Export Premium-Check Entfernung**

**Datei:** `smali_classes3/e8/j$a.smali`

**Methode:** `e(Ly0/c;Ls7/a;)Z` (Zeilen 267-332)

**Änderung:**
```smali
# ALT: ~65 Zeilen mit Premium & Trial Checks
invoke-static {}, Lcom/calimoto/calimoto/parse/user/a;->Q()Z  # isPremium Check
if-nez v0, :cond_1                                           # if NOT Premium
invoke-static {}, Lcom/calimoto/calimoto/parse/user/a;->K()Z  # hasFreeTrialOrPromo Check
if-eqz v0, :cond_0                                           # if NOT Trial
# ... Paywall Dialog anzeigen mit k() Methode ...
return p0  # return true (zeige Dialog)

# NEU: Direkt ohne Checks
const/4 p0, 0x0
return p0  # return false (kein Dialog, erlaube Export)
```

**Reason:** Diese Methode kontrolliert, ob der GPX-Export ein Premium-Dialog zeigen soll:
- `return 0` (false) = Kein Dialog → Export erlaubt
- `return 1` (true) = Dialog zeigen → Premium-Paywall

**Effekt:** 
- GPX-Export ist für ALLE Nutzer verfügbar
- Keine Premium-Aufforderung mehr beim Export
- Logging-Events werden weiterhin registriert

**Risiko:** Niedrig - Pure Feature-Unlock, keine Security-Implikationen

---

### 1. XML-Konfiguration (Firebase Remote Config)

**Datei:** `res/xml/remote_config_defaults.xml`

```xml
SUCHE nach:
<key>skipPaywallInfoPercentAndroid</key>
<value>0.5</value>

ERSETZE mit:
<key>skipPaywallInfoPercentAndroid</key>
<value>1.0</value>
```

**Grund:** Setzt den Paywall-Skip auf 100% für alle Nutzer
**Risiko:** Minimal - Config-basiert, leicht reversibel
**Anwendbarkeit:** Sollte in allen Versionen ähnlich sein

---

### 2. Smali Code - Navigation Premium-Check #1

**Datei:** `smali_classes3/com/calimoto/calimoto/premium/featureview/ActivityFeatureView.smali`

**Suchmuster:** Methode `v0()` (onCreate)

```smali
SUCHE nach:
    sget-object v2, Le8/j;->a:Le8/j$a;
    invoke-virtual {v2}, Le8/j$a;->f()Z
    move-result v2
    invoke-virtual {v0}, Lcom/calimoto/calimoto/premium/featureview/ActivityFeatureView;->q0()Lcom/calimoto/calimoto/premium/featureview/a;

ERSETZE mit:
    const/4 v2, 0x1
    invoke-virtual {v0}, Lcom/calimoto/calimoto/premium/featureview/ActivityFeatureView;->q0()Lcom/calimoto/calimoto/premium/featureview/a;
```

**Kontext:**
- Befindet sich in der `v0()` Compose-Funktionin Zeile ~645
- Setzt Premium-Check für Navigation UI auf true
- Wird aufgerufen beim App-Start in der Feature-View Aktivität

**Grund:** Entfernt die Premium-Status-Überprüfung
**Effekt:** Navigation wird immer gerendert, unabhängig vom Account-Status

---

### 3. Smali Code - Navigation Premium-Check #2

**Datei:** `smali_classes3/j7/r0.smali`

**Suchmuster:** TimelineScreen render Methode

```smali
SUCHE nach (Labelzusammenhang):
    :goto_15
    sget-object v7, Le8/j;->a:Le8/j$a;
    invoke-virtual {v7}, Le8/j$a;->f()Z
    move-result v7
    sget-object v8, Lkotlin/Unit;->a:Lkotlin/Unit;
    invoke-interface {v13, v5}, Landroidx/compose/runtime/Composer;->changedInstance(Ljava/lang/Object;)Z

ERSETZE mit:
    :goto_15
    const/4 v7, 0x1
    sget-object v8, Lkotlin/Unit;->a:Lkotlin/Unit;
    invoke-interface {v13, v5}, Landroidx/compose/runtime/Composer;->changedInstance(Ljava/lang/Object;)Z
```

**Kontext:**
- TimelineScreen Compose-Rendering
- Zweiter Ort, wo Navigation Premium-Checks durchgeführt werden
- Die Zeile "com.calimoto.calimoto.premium.timeline.ui.TimeLineScreenContent" ist in der Nähe

**Grund:** Entfernt zweiten Premium-Status-Check
**Effekt:** Navigation UI wird immer komplett gerendert

---

---

## 📝 Schritt-für-Schritt Anleitung für neue Versionen

### Voraussetzungen:
- apktool
- apksigner
-

### Prozess:

**Schritt 0 (NEU): GPX Export ändern**
```properties
cd extracted_app
gedit smali_classes3/e8/j$a.smali
# Suche nach Methode: .method public final e(Ly0/c;Ls7/a;)Z
# Ersetze die gesamte Methode mit direkt return false (0x0)
```

**Schritt 1: XML-Config ändern**
```properties
cd extracted_app
gedit res/xml/remote_config_defaults.xml
# Ändere skipPaywallInfoPercentAndroid von 0.5 zu 1.0
```

**Schritt 2: Erste Smali-Datei ändern**
```properties
gedit smali_classes3/com/calimoto/calimoto/premium/featureview/ActivityFeatureView.smali
# Suche nach: invoke-virtual {v2}, Le8/j$a;->f()Z
# Ersetze den Block wie oben
```

**Schritt 3: Zweite Smali-Datei ändern**
```properties
gedit smali_classes3/j7/r0.smali
# Suche nach: :goto_15 gefolgt von Le8/j$a;->f()Z
# Ersetze den Block wie oben
```

**Schritt 4: Profil-Layout ändern**
```properties
gedit res/layout/fragment_profile_details.xml
# Kommentiere die profile_account_compose_view wie oben
```

**Schritt 5: Rebuild & Sign**
```properties
apktool b -o calimoto-modified.apk calimoto_app

# one time
# keytool -genkeypair -v -keystore mein-key.keystore -alias meinalias -keyalg RSA -keysize 2048 -validity 10000

apksigner sign --ks mein-key.keystore --ks-key-alias meinalias calimoto-modified.apk

apksigner verify calimoto-modified.apk
```

---

## 🔍 Wie man Änderungen in neuen Versionen findet

Wenn die App-Version aktualisiert wird:

### **0. GPX Export Patch**
- Suche nach: `Le8/j$a;->e(` oder Klassen in `e8/j$a.smali`
- Methode `e()` kontrolliert den Premium-Check für Export
- Sollte in den meisten Versionen existieren

### 1. **Remote Config Datei**
- Pfad bleibt meist gleich: `res/xml/remote_config_defaults.xml`
- Suche nach: `skipPaywallInfoPercentAndroid`
- Sollte trivial zu finden sein

### 2. **ActivityFeatureView.smali**
- Suche nach: `Le8/j$a;->f()Z` (Premium-Check Methode)
- Die Methode existiert wahrscheinlich immer noch
- Wenn Smali-Klassennamen sich ändern, suche nach "ActivityFeatureView" + "premium"

### 3. **r0.smali oder ähnlich**
- Dieser Name könnte obfuskiert sein
- Suche nach Dateien mit: `Le8/j$a;->f()Z`
- Oder suche nach: `TimeLineScreenContent` oder `premium.timeline`

### 4. **fragment_profile_details.xml**
- Pfad sollte stabil sein
- Falls nicht gefunden, suche nach Profile + Compose-View
- ID `profile_account_compose_view` ist charakteristisch

---


## 🚀 Automatisiertes Patching (Optional)

Für zukünftige Versionen könnte ein Python-Script erstellt werden:

```python
# pseudo-code
def apply_calimoto_patches(extracted_app_dir):
    # 0. Patch GPX Export
    patch_smali(f"{extracted_app_dir}/smali_classes3/e8/j$a.smali",
                "method e() with premium checks", "return false directly")
    
    # 1. Patch Remote Config
    patch_xml(f"{extracted_app_dir}/res/xml/remote_config_defaults.xml",
              "skipPaywallInfoPercentAndroid", "0.5", "1.0")

    # 2. Find and patch smali files with Le8/j$a;->f()Z
    for smali_file in find_files_with(extracted_app_dir, "Le8/j$a"):
        patch_smali_premium_check(smali_file)

    # 3. Patch profile layout
    patch_xml(f"{extracted_app_dir}/res/layout/fragment_profile_details.xml",
              "profile_account_compose_view", "<!-- kommentieren -->")

    print("✅ Patches angewendet!")
```

---

## 📞 Troubleshooting

**Problem:** GPX Export zeigt trotzdem Paywall
**Lösung:** Stelle sicher, dass `smali_classes3/e8/j$a.smali` Methode `e()` korrekt gepatcht wurde - sollte direkt mit `const/4 p0, 0x0; return p0` enden

**Problem:** Smali-Datei nicht gefunden
**Lösung:** Klasse wurde möglicherweise umbenannt. Suche nach der Methode `Le8/j$a;->f()Z`

**Problem:** Layout-Datei hat andere Struktur
**Lösung:** Die ID sollte gleich sein. Suche nach `profile_account_compose_view`

**Problem:** Premium-Dialoge erscheinen trotzdem
**Lösung:** Alle Smali-Änderungen wurden angewendet? Prüfe logcat auf andere Premium-Checks

---

## 📌 Summary für schnelle Referenz

```
0. Smali GPX: e8/j$a.smali Methode e() → return false
1. XML:       0.5 → 1.0 in remote_config_defaults.xml
2. Smali #1:  Le8/j$a;->f()Z aufrufe ersetzen mit const/4 v2, 0x1
3. Smali #2:  Le8/j$a;->f()Z aufrufe ersetzen mit const/4 v7, 0x1
```

Fertig! 🎉


**Datei:** `res/xml/remote_config_defaults.xml`

```xml
SUCHE nach:
<key>skipPaywallInfoPercentAndroid</key>
<value>0.5</value>

ERSETZE mit:
<key>skipPaywallInfoPercentAndroid</key>
<value>1.0</value>
```

**Grund:** Setzt den Paywall-Skip auf 100% für alle Nutzer
**Risiko:** Minimal - Config-basiert, leicht reversibel
**Anwendbarkeit:** Sollte in allen Versionen ähnlich sein

---

### 2. Smali Code - Navigation Premium-Check #1

**Datei:** `smali_classes3/com/calimoto/calimoto/premium/featureview/ActivityFeatureView.smali`

**Suchmuster:** Methode `v0()` (onCreate)

```smali
SUCHE nach:
    sget-object v2, Le8/j;->a:Le8/j$a;
    invoke-virtual {v2}, Le8/j$a;->f()Z
    move-result v2
    invoke-virtual {v0}, Lcom/calimoto/calimoto/premium/featureview/ActivityFeatureView;->q0()Lcom/calimoto/calimoto/premium/featureview/a;

ERSETZE mit:
    const/4 v2, 0x1
    invoke-virtual {v0}, Lcom/calimoto/calimoto/premium/featureview/ActivityFeatureView;->q0()Lcom/calimoto/calimoto/premium/featureview/a;
```

**Kontext:**
- Befindet sich in der `v0()` Compose-Funktionin Zeile ~645
- Setzt Premium-Check für Navigation UI auf true
- Wird aufgerufen beim App-Start in der Feature-View Aktivität

**Grund:** Entfernt die Premium-Status-Überprüfung
**Effekt:** Navigation wird immer gerendert, unabhängig vom Account-Status

---

### 3. Smali Code - Navigation Premium-Check #2

**Datei:** `smali_classes3/j7/r0.smali`

**Suchmuster:** TimelineScreen render Methode

```smali
SUCHE nach (Labelzusammenhang):
    :goto_15
    sget-object v7, Le8/j;->a:Le8/j$a;
    invoke-virtual {v7}, Le8/j$a;->f()Z
    move-result v7
    sget-object v8, Lkotlin/Unit;->a:Lkotlin/Unit;
    invoke-interface {v13, v5}, Landroidx/compose/runtime/Composer;->changedInstance(Ljava/lang/Object;)Z

ERSETZE mit:
    :goto_15
    const/4 v7, 0x1
    sget-object v8, Lkotlin/Unit;->a:Lkotlin/Unit;
    invoke-interface {v13, v5}, Landroidx/compose/runtime/Composer;->changedInstance(Ljava/lang/Object;)Z
```

**Kontext:**
- TimelineScreen Compose-Rendering
- Zweiter Ort, wo Navigation Premium-Checks durchgeführt werden
- Die Zeile "com.calimoto.calimoto.premium.timeline.ui.TimeLineScreenContent" ist in der Nähe

**Grund:** Entfernt zweiten Premium-Status-Check
**Effekt:** Navigation UI wird immer komplett gerendert

---

---

## 📝 Schritt-für-Schritt Anleitung für neue Versionen

### Voraussetzungen:
- apktool
- apksigner
-

### Prozess:

**Schritt 1: XML-Config ändern**
```properties
cd extracted_app
gedit res/xml/remote_config_defaults.xml
# Ändere skipPaywallInfoPercentAndroid von 0.5 zu 1.0
```

**Schritt 2: Erste Smali-Datei ändern**
```properties
gedit smali_classes3/com/calimoto/calimoto/premium/featureview/ActivityFeatureView.smali
# Suche nach: invoke-virtual {v2}, Le8/j$a;->f()Z
# Ersetze den Block wie oben
```

**Schritt 3: Zweite Smali-Datei ändern**
```properties
gedit smali_classes3/j7/r0.smali
# Suche nach: :goto_15 gefolgt von Le8/j$a;->f()Z
# Ersetze den Block wie oben
```

**Schritt 4: Profil-Layout ändern**
```properties
gedit res/layout/fragment_profile_details.xml
# Kommentiere die profile_account_compose_view wie oben
```

**Schritt 5: Rebuild & Sign**
```properties
apktool b -o calimoto-modified.apk calimoto_app

# one time
# keytool -genkeypair -v -keystore mein-key.keystore -alias meinalias -keyalg RSA -keysize 2048 -validity 10000

apksigner sign --ks mein-key.keystore --ks-key-alias meinalias calimoto-modified.apk

apksigner verify calimoto-modified.apk
```

---

## 🔍 Wie man Änderungen in neuen Versionen findet

Wenn die App-Version aktualisiert wird:

### 1. **Remote Config Datei**
- Pfad bleibt meist gleich: `res/xml/remote_config_defaults.xml`
- Suche nach: `skipPaywallInfoPercentAndroid`
- Sollte trivial zu finden sein

### 2. **ActivityFeatureView.smali**
- Suche nach: `Le8/j$a;->f()Z` (Premium-Check Methode)
- Die Methode existiert wahrscheinlich immer noch
- Wenn Smali-Klassennamen sich ändern, suche nach "ActivityFeatureView" + "premium"

### 3. **r0.smali oder ähnlich**
- Dieser Name könnte obfuskiert sein
- Suche nach Dateien mit: `Le8/j$a;->f()Z`
- Oder suche nach: `TimeLineScreenContent` oder `premium.timeline`

### 4. **fragment_profile_details.xml**
- Pfad sollte stabil sein
- Falls nicht gefunden, suche nach Profile + Compose-View
- ID `profile_account_compose_view` ist charakteristisch

---


## 🚀 Automatisiertes Patching (Optional)

Für zukünftige Versionen könnte ein Python-Script erstellt werden:

```python
# pseudo-code
def apply_calimoto_patches(extracted_app_dir):
    # 1. Patch Remote Config
    patch_xml(f"{extracted_app_dir}/res/xml/remote_config_defaults.xml",
              "skipPaywallInfoPercentAndroid", "0.5", "1.0")

    # 2. Find and patch smali files with Le8/j$a;->f()Z
    for smali_file in find_files_with(extracted_app_dir, "Le8/j$a"):
        patch_smali_premium_check(smali_file)

    # 3. Patch profile layout
    patch_xml(f"{extracted_app_dir}/res/layout/fragment_profile_details.xml",
              "profile_account_compose_view", "<!-- kommentieren -->")

    print("✅ Patches angewendet!")
```

---

## 📞 Troubleshooting

**Problem:** Smali-Datei nicht gefunden
**Lösung:** Klasse wurde möglicherweise umbenannt. Suche nach der Methode `Le8/j$a;->f()Z`

**Problem:** Layout-Datei hat andere Struktur
**Lösung:** Die ID sollte gleich sein. Suche nach `profile_account_compose_view`

**Problem:** Premium-Dialoge erscheinen trotzdem
**Lösung:** Beide Smali-Änderungen wurden angewendet? Prüfe logcat auf andere Premium-Checks

---

## 📌 Summary für schnelle Referenz

```
1. XML:      0.5 → 1.0 in remote_config_defaults.xml
2. Smali #1: Le8/j$a;->f()Z aufrufe ersetzen mit const/4 v2, 0x1
3. Smali #2: Le8/j$a;->f()Z aufrufe ersetzen mit const/4 v7, 0x1
```

Fertig! 🎉
