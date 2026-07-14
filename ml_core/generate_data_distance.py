import numpy as np
import pandas as pd
import time
import requests
import math
import os

# Bounding box approximative du Grand Tunis (Tunis, Ariana, Ben Arous, Manouba)
LAT_MIN, LAT_MAX = 36.72, 36.92
LNG_MIN, LNG_MAX = 10.05, 10.32

def calculer_haversine(lat1, lng1, lat2, lng2):
    """Calcule la distance à vol d'oiseau en kilomètres"""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def recuperer_distance_osrm(lat1, lng1, lat2, lng2):
    """Appelle l'API publique OSRM pour avoir la vraie distance routière"""
    url = f"http://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=false"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('routes'):
                # OSRM renvoie la distance en mètres, on la convertit en km
                return data['routes'][0]['distance'] / 1000.0
    except Exception as e:
        print(f"Erreur OSRM : {e}")
    return None

print(" Début de la génération du dataset de distances...")
data_samples = []
NB_SAMPLES = 1500  # Commencez par 1000 pour test

for i in range(NB_SAMPLES):
    # Génération de deux points aléatoires dans le Grand Tunis
    lat1 = np.random.uniform(LAT_MIN, LAT_MAX)
    lng1 = np.random.uniform(LNG_MIN, LNG_MAX)
    lat2 = np.random.uniform(LAT_MIN, LAT_MAX)
    lng2 = np.random.uniform(LNG_MIN, LNG_MAX)
    
    dist_hav = calculer_haversine(lat1, lng1, lat2, lng2)
    dist_reelle = recuperer_distance_osrm(lat1, lng1, lat2, lng2)
    
    if dist_reelle is not None:
        data_samples.append({
            'lat1': lat1, 'lng1': lng1,
            'lat2': lat2, 'lng2': lng2,
            'distance_haversine': dist_hav,
            'distance_reelle_osrm': dist_reelle
        })
    
    # Respect du rate limit de l'API OSRM publique (1 requête par seconde recommandé)
    time.sleep(1.0)
    if (i + 1) % 50 == 0:
        print(f" {i + 1} paires générées...")

df = pd.DataFrame(data_samples)

# Récupère le dossier où se trouve le script actuel (ml_core)
dossier_actuel = os.path.dirname(os.path.abspath(__file__))
chemin_sauvegarde = os.path.join(dossier_actuel, 'dataset_distances_tunis.csv')


df = pd.DataFrame(data_samples)

# Récupère le dossier où se trouve le script actuel (ml_core)
dossier_actuel = os.path.dirname(os.path.abspath(__file__))
chemin_sauvegarde = os.path.join(dossier_actuel, 'dataset_distances_tunis.csv')

# Sauvegarde sécurisée
df.to_csv(chemin_sauvegarde, index=False)
print(f"🎉 Dataset de distances sauvegardé avec succès sous : {chemin_sauvegarde} ({len(df)} lignes) !")