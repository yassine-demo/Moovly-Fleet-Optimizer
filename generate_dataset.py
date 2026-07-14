import numpy as np
import pandas as pd
import json
import os
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# --- CONSTANTES GÉOGRAPHIQUES (Grand Tunis) ---
DESTINATION_CENTRALE = {'lat': 36.8065, 'lng': 10.1815}  # Exemple : Centre-ville / Zone d'activité

def distance_haversine_km(lat1, lon1, lat2, lon2):
    """Calcule la distance à vol d'oiseau entre deux points GPS[cite: 8]."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- SOLVEUR SIMPLIFIÉ POUR ÉVALUATION RAPIDE ---
def evaluer_flotte_ortools(employes, destination, capacites_vehicules):
    """ Exécute OR-Tools avec un mix de capacités spécifique et retourne la distance totale[cite: 19, 21]. """
    nodes = employes + [destination]
    dest_idx = len(nodes) - 1
    n_employees = len(employes)
    max_vehicles = len(capacites_vehicules)

    manager = pywrapcp.RoutingIndexManager(len(nodes), max_vehicles, dest_idx)
    routing = pywrapcp.RoutingModel(manager)

    def get_dist(i, j):
        a, b = nodes[i], nodes[j]
        # Utilisation de la distance Haversine avec le facteur correcteur de Tunis [cite: 20]
        return int(distance_haversine_km(a['lat'], a['lng'], b['lat'], b['lng']) * 1300)

    def distance_callback(from_idx, to_idx):
        return get_dist(manager.IndexToNode(from_idx), manager.IndexToNode(to_idx))

    transit_cb = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    def demand_callback(idx):
        return 1 if manager.IndexToNode(idx) < n_employees else 0  # [cite: 21]
    
    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
    # Remplacement de la capacité unique par notre vecteur dynamique hétérogène 
    routing.AddDimensionWithVehicleCapacity(demand_cb, 0, capacites_vehicules, True, "Capacity")

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC  # [cite: 21]
    search_parameters.time_limit.seconds = 2  # Temps court pour la génération en boucle

    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        return solution.ObjectiveValue() / 1000.0  # Distance convertie en kilomètres
    return float('inf')

# --- EXTRACTION DES FEATURES (INPUTS) ---
def extraire_features_groupe(employes, destination):
    """ Transforme un groupe de coordonnées d'employés en variables statistiques (Features) """
    lats = [e['lat'] for e in employes]
    lngs = [e['lng'] for e in employes]
    distances = [distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']) for e in employes]
    
    features = {
        'n_employes': len(employes),
        'dist_moyenne': np.mean(distances),
        'dist_std': np.std(distances),
        'dist_max': np.max(distances),
        'dispersion_lat': np.std(lats),
        'dispersion_lng': np.std(lngs),
        'bbox_area': (max(lats) - min(lats)) * (max(lngs) - min(lngs)) * 111 * 111  # Surface approx en km²
    }
    return features

# --- GÉNÉRATION DU DATASET ---
def generer_dataset_strategies(n_scenarios=250):
    dataset = []
    print(f"Début de la génération empirique de {n_scenarios} scénarios...")

    # Définition de nos 4 profils stratégiques de flottes candidats
    # Pour chaque profil, on génère un pool large de véhicules adaptés au besoin
    for sim in range(n_scenarios):
        # 1. Générer un nombre aléatoire d'employés (ex: entre 6 et 24)
        n_emp = np.random.randint(6, 25)
        
        # Dispersion aléatoire simulant des quartiers du Grand Tunis (Ariana, Ben Arous, Bardo...)
        center_lat = DESTINATION_CENTRALE['lat'] + np.random.uniform(-0.04, 0.04)
        center_lng = DESTINATION_CENTRALE['lng'] + np.random.uniform(-0.04, 0.04)
        
        employes = []
        for i in range(n_emp):
            employes.append({
                'lat': center_lat + np.random.normal(0, 0.015),
                'lng': center_lng + np.random.normal(0, 0.015)
            })

        # Extraire les caractéristiques géographiques de ce groupe
        features = extraire_features_groupe(employes, DESTINATION_CENTRALE)

        # 2. Brute-forcer nos profils de flottes candidats pour voir lequel minimise la distance réelle
        # Nombre théorique maximal de véhicules nécessaires
        max_v = n_emp 

        strategies_candidats = {
            0: [4] * max_v,                                     # Stratégie 0 : Uniquement des Taxis de 4 places
            1: [3] * max_v,                                     # Stratégie 1 : Uniquement des Taxis de 3 places
            2: [2] * max_v,                                     # Stratégie 2 : Uniquement des Taxis de 2 places
            3: [4 if i % 2 == 0 else 2 for i in range(max_v)]  # Stratégie 3 : Mix alterné 50% de 4 places / 50% de 2 places
        }

        meilleure_strategie = None
        meilleure_distance = float('inf')

        for strat_id, flotte in strategies_candidats.items():
            dist_obtenue = evaluer_flotte_ortools(employes, DESTINATION_CENTRALE, flotte)
            if dist_obtenue < meilleure_distance:
                meilleure_distance = dist_obtenue
                meilleure_strategie = strat_id

        # Sauvegarder si une solution valide a été trouvée
        if meilleure_strategie is not None:
            features['label_strategie_flotte'] = meilleure_strategie
            features['meilleure_distance_km'] = meilleure_distance
            dataset.append(features)

        if (sim + 1) % 50 == 0:
            print(f" Scénarios simulés et mesurés : {sim + 1}/{n_scenarios}")

    df = pd.DataFrame(dataset)
    df.to_csv("ml_core/dataset_fleet_optimization.csv", index=False)
    print("Dataset généré avec succès et enregistré dans 'ml_core/dataset_fleet_optimization.csv' !")

if __name__ == "__main__":
    os.makedirs("ml_core", exist_ok=True)
    generer_dataset_strategies(250)