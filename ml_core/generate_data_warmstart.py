import numpy as np
import pandas as pd
import os
import sys
import random
import math
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import moovly_system as ms

# 1. Configuration de la simulation
NB_SIMULATIONS = 60  # Nombre de scénarios de transport à simuler
DESTINATION_TUNIS = {'nom': 'Bureau Moovly', 'lat': 36.8065, 'lng': 10.1815, '_id': 'dest_bureau'}

def distance_haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

pair_samples = []

print(" Génération des scénarios de tournées via OR-Tools...")

for sim in range(NB_SIMULATIONS):
    # Générer un nombre réaliste d'employés (ex: entre 15 et 35) éparpillés autour de Tunis
    nb_emp = random.randint(15, 35)
    employes = []
    
    for i in range(nb_emp):
        lat = DESTINATION_TUNIS['lat'] + random.uniform(-0.08, 0.08)
        lng = DESTINATION_TUNIS['lng'] + random.uniform(-0.08, 0.08)
        employes.append({
            'id': f'E_{sim}_{i}',
            'nom': f'Employé_{sim}_{i}',
            'lat': lat,
            'lng': lng,
            'Ing': lng,  # Double stockage pour éviter les conflits d'encodage lng/Ing
            '_id': f'emp_{sim}_{i}'
        })
    
# On force OR-Tools à chercher un peu plus (5 secondes) pour avoir une excellente solution de référence
    ms.PARAMS_ALGO['ortools_time_limit_s'] = 20
    
    # Appel direct au solveur sans argument optionnel de temps pour éviter les conflits de signature
    routes = ms.solve_vrp_ortools(employes, DESTINATION_TUNIS, capacite=4)
    
    if not routes:
        continue
        
    # On crée une map pour savoir à quelle route (index) appartient chaque employé
    emp_to_route_idx = {}
    for r_idx, route in enumerate(routes):
        for emp in route:
            emp_to_route_idx[emp['id']] = r_idx
            
    # Échantillonner des paires d'employés au hasard pour cette simulation
    for _ in range(120): 
        empA = random.choice(employes)
        empB = random.choice(employes)
        if empA['id'] == empB['id']:
            continue
            
        dist_entre_eux = distance_haversine(empA['lat'], empA['lng'], empB['lat'], empB['lng'])
        dist_A_dest = distance_haversine(empA['lat'], empA['lng'], DESTINATION_TUNIS['lat'], DESTINATION_TUNIS['lng'])
        dist_B_dest = distance_haversine(empB['lat'], empB['lng'], DESTINATION_TUNIS['lat'], DESTINATION_TUNIS['lng'])
        
        # Le solveur OR-Tools les a-t-il groupés ensemble ? (1 = Oui, 0 = Non)
        route_A = emp_to_route_idx.get(empA['id'])
        route_B = emp_to_route_idx.get(empB['id'])
        sont_ensemble = 1 if (route_A is not None and route_A == route_B) else 0
        
        pair_samples.append({
            'dist_entre_employes': dist_entre_eux,
            'dist_A_destination': dist_A_dest,
            'dist_B_destination': dist_B_dest,
            'taille_groupe_total': nb_emp, # Utile pour que l'IA comprenne la densité globale du problème
            'sont_ensemble': sont_ensemble
        })

# Sauvegarde finale sécurisée
if pair_samples:
    df_pairs = pd.DataFrame(pair_samples)
    dossier_actuel = os.path.dirname(os.path.abspath(__file__))
    chemin_sauvegarde = os.path.join(dossier_actuel, 'dataset_warmstart_pairs.csv')
    df_pairs.to_csv(chemin_sauvegarde, index=False)
    print(f" {len(df_pairs)} paires de données générées et sauvegardées dans {chemin_sauvegarde}")
else:
    print(" Erreur : Aucune donnée n'a pu être collectée.")