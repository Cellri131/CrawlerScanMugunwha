from PIL import Image
import os

def fusionner_pages(folder="pages", max_height=32000):
    # Récupération et tri des fichiers page_XXX.png
    files = sorted([
        f for f in os.listdir(folder)
        if f.startswith("page_") and f.endswith(".png")
    ])

    # Ignorer page_001.png
    files = [f for f in files if f != "page_001.png"]

    if not files:
        raise ValueError("Aucune image à fusionner après exclusion de page_001.png.")

    # Chargement des images restantes
    images = [Image.open(os.path.join(folder, f)) for f in files]

    # Largeur identique, hauteur totale = somme des hauteurs
    width, _ = images[0].size
    total_height = sum(img.height for img in images)

    # Création de la grande image finale
    result = Image.new("RGB", (width, total_height))

    # Collage des images les unes sous les autres
    y_offset = 0
    for img in images:
        result.paste(img, (0, y_offset))
        y_offset += img.height

    # Découpage si dépasse max_height
    output_paths = []
    if total_height > max_height:
        # Nombre de morceaux nécessaires
        num_parts = (total_height + max_height - 1) // max_height

        for i in range(num_parts):
            top = i * max_height
            bottom = min(top + max_height, total_height)

            # Découpe
            part = result.crop((0, top, width, bottom))

            output_path = os.path.join(folder, f"page_all{i+1}.png")
            part.save(output_path)
            output_paths.append(output_path)

        return output_paths

    else:
        # Sauvegarde unique si pas besoin de découper
        output_path = os.path.join(folder, "page_all.png")
        result.save(output_path)
        return [output_path]
