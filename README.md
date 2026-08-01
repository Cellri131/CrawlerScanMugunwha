# MugunwHa Trad

**MugunwHa Trad** est une application Windows (.exe) qui automatise le traitement d’un chapitre de manhwa : téléchargement des pages, détection des bulles, OCR, traduction automatique, édition et export DOCX.

---

## Fonctionnalités

- **Scan automatique** : saisie d’une URL de chapitre → téléchargement des images.
- **Détection des bulles** : OpenCV détecte les zones de texte (bulles / hors-bulles).
- **OCR** : Tesseract extrait le texte (anglais par défaut).
- **Classification** :
  - texte en bulle → ligne normale
  - texte hors bulle → ligne terminée par `**`
- **Édition** : tableau éditable pour corriger ou ajuster le texte.
- **Traduction** : traduction automatique EN → FR (Google Translate API).
- **Export** : export du texte final en fichier DOCX.

---

## Interface (aperçu)

- **Panneau gauche** : affichage des pages téléchargées.
- **Panneau central** : tableau éditable contenant le texte extrait.
- **Panneau droit** : traduction ligne par ligne.
- **Barres de progression** : pour le téléchargement et la traduction.

---

## Raccourcis et commandes utiles

- **Double‑clic** : éditer une ligne.  
- **Entrée** : insérer une ligne vide sous la ligne sélectionnée.  
- **Backspace** : fusionner la ligne courante avec la précédente.  
- **Suppr** : supprimer la ligne sélectionnée.  
- **Touche E** : ajouter `**` à la fin de la ligne (marqueur hors-bulle).

---

## Utilisation (version .exe)

1. Placez le dossier contenant l’exécutable et les ressources nécessaires (voir section suivante).  
2. Double‑cliquez sur `MugunwHaTrad.exe` pour lancer l’application.  
3. Collez l’URL du chapitre dans le champ URL.  
4. Cliquez sur **Lancer** → le téléchargement et l’OCR démarrent.  
5. Cliquez sur **Traduire** pour obtenir la version française.  
6. Cliquez sur **Exporter DOCX** pour générer le document final.

---

## Fichiers requis (dans le même dossier que l’exécutable)

- `manhwa_crawler.py` (script du crawler)  
- `pages/` (dossier où les images sont sauvegardées)  
- `cara/` (templates police, optionnel)  
- `tesseract/` ou installation Tesseract accessible (si non installé système)  
- `chromedriver.exe` (ou driver compatible dans le PATH)  

> Remarque : la version fournie en `.exe` peut être distribuée en mode **onedir** (recommandé) pour conserver ces fichiers à côté de l’exécutable. En `--onefile`, l’exécution de scripts externes via subprocess n’est pas fiable.

---

## Dépendances (pour la version Python / développement)

- Python 3.x  
- tkinter  
- selenium  
- webdriver-manager  
- requests  
- beautifulsoup4  
- pillow (PIL)  
- opencv-python  
- numpy  
- pytesseract  
- (optionnel) packages pour l’export DOCX

---

## Packaging recommandé

Pour un exécutable stable qui appelle `manhwa_crawler.py` en subprocess, **utiliser PyInstaller en mode `--onedir`** :

```bash
pyinstaller --onedir --windowed --icon MugunwHaLogoTrad.ico ihm.py
