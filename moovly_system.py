"""
🚗 MOOVLY OPTIMIZER — VERSION SANS TAXIS
==========================================
Optimise l'ordre de ramassage des employés vers une destination.
Algorithme : Clustering avec contrainte de capacité, en commençant 
par l'employé le plus loin de la destination.
"""

import numpy as np
import pandas as pd
import math
import json
import requests
import time
from io import BytesIO

import joblib
import os
import warnings


#CHARGEMENT DES MODÈLES ML
warnings.filterwarnings("ignore", message="X does not have valid feature names")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_DIST_MODEL = os.path.join(BASE_DIR, 'ml_core', 'model_distance.pkl')
PATH_FLEET_MODEL = os.path.join(BASE_DIR, 'ml_core', 'model_fleet_strategy.pkl')
MODEL_FLEET = None
MODEL_DISTANCE = None

try:
    if os.path.exists(PATH_DIST_MODEL):
        MODEL_DISTANCE = joblib.load(PATH_DIST_MODEL)
        print("[ML] Modèle de prédiction des distances chargé avec succès.")
    if os.path.exists(PATH_FLEET_MODEL):
        MODEL_FLEET = joblib.load(PATH_FLEET_MODEL)
        print("[ML] Modèle de stratégie de flotte chargé avec succès.")
except Exception as e:
    print(f"[ML] Erreur lors du chargement des modèles : {e}")

# =============================================================================
# CHARGEMENT EXCEL
# =============================================================================




def _extraire_features_flotte(employes, destination):
    if not employes:
        return None
    lats = [e['lat'] for e in employes]
    lngs = [e['lng'] for e in employes]
    distances = [distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']) for e in employes]
    return [len(employes), float(np.mean(distances)), float(np.std(distances)), float(np.max(distances)), float(np.std(lats)), float(np.std(lngs)), float((max(lats) - min(lats)) * (max(lngs) - min(lngs)) * 111 * 111)]


def predire_flotte_ia(employes, destination):
    if not employes:
        return []
    if MODEL_FLEET is None:
        return construire_flotte_par_defaut(len(employes))
    features = _extraire_features_flotte(employes, destination)
    if features is None:
        return construire_flotte_par_defaut(len(employes))
    try:
        prediction = int(MODEL_FLEET.predict([features])[0])
    except Exception as exc:
        print(f"[ML] Erreur prédiction flotte: {exc}")
        return construire_flotte_par_defaut(len(employes))
    n_employees = len(employes)
    if prediction == 0:
        pool = [4] * max(1, math.ceil(n_employees / 4))
    elif prediction == 3:
        pool = [4, 2] * max(1, math.ceil(n_employees / 2))
    else:
        pool = [3] * max(1, math.ceil(n_employees / 3))
    while sum(pool) < n_employees:
        pool.append(1)
    pool = pool[:max(1, n_employees)]
    pool.sort(reverse=True)
    print(f"[ML] Flotte prédite (label {prediction}) : {pool}")
    return pool


def preparer_capacite_flotte(capacite, employes, destination):
    if isinstance(capacite, str) and capacite.lower() == 'ia':
        return predire_flotte_ia(employes, destination)
    if isinstance(capacite, (list, tuple)):
        return list(capacite)
    return int(capacite)

def charger_destinations_excel(filepath):
    """Charge les destinations depuis le fichier Excel."""
    try:
        df = pd.read_excel(filepath)
        destinations = []
        for i, row in df.iterrows():
            nom = str(row.get('Destination', '')).strip()
            if nom and nom != 'nan':
                destinations.append({
                    'nom': nom,
                    'lat': None,
                    'lng': None,
                    '_id': f'dest_{i}'
                })
        return destinations
    except Exception as e:
        print(f"❌ Erreur lecture Excel: {e}")
        return []

def charger_employes_excel(filepath):
    """Charge les employés depuis un fichier Excel."""
    try:
        import pandas as pd
        df = pd.read_excel(filepath)
        
        # Trouver la colonne destination (tolérance majuscules/pluriel)
        dest_col = None
        for col in df.columns:
            if str(col).lower().strip() in ['destination', 'destinations']:
                dest_col = col
                break
                
        if not dest_col:
            raise ValueError("Le fichier Excel doit obligatoirement contenir une colonne 'Destination' (ou 'destination', 'destinations').")
            
        employes = []
        for i, row in df.iterrows():
            nom = str(row.get('Nom', row.get('nom', f'Employé {i+1}'))).strip()
            lat = row.get('Latitude', row.get('lat', None))
            lng = row.get('Longitude', row.get('lng', row.get('lon', None)))
            # Nouvelle colonne: 'Destination' (qui est en fait la résidence de l'employé)
            residence = str(row.get(dest_col, '')).strip()
            
            if nom and nom != 'nan':
                employes.append({
                    'id': f'E{i+1}',
                    'nom': nom,
                    'residence': residence if residence != 'nan' else None,
                    'lat': float(lat) if pd.notna(lat) else None,
                    'lng': float(lng) if pd.notna(lng) else None,
                    '_id': f'emp_{i}'
                })
        return employes
    except ValueError as ve:
        raise ve
    except Exception as e:
        print(f"❌ Erreur lecture Excel employés: {e}")
        return []

# GÉOCODAGE AUTOMATIQUE (GOOGLE MAPS)

GEOCODE_CACHE = {}

def geocoder_lieu(nom_lieu, ville="Tunis, Tunisia"):
    """Convertit un nom de lieu en coordonn\u00e9es GPS via Nominatim (forc\u00e9 Tunisie)."""
    import re
    
    cache_key = f"{nom_lieu}_{ville}"
    if cache_key in GEOCODE_CACHE:
        return GEOCODE_CACHE[cache_key]
    
    # Pré-traitement du nom
    clean_nom = re.sub(r'\(.*?\)', '', nom_lieu).strip()
    clean_nom = re.sub(r'(\d+)', r' \1', clean_nom).strip()
    clean_nom = clean_nom.replace("Sup", "Sup\u00e9rieure").replace("  ", " ")
    
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'MoovlyApp/1.0'}
    
    # Variantes de recherche, toutes restreintes à la Tunisie
    variantes = [
        f"{clean_nom}, {ville}",
        f"{nom_lieu}, {ville}",
        f"{clean_nom}, Tunis",
        clean_nom,
    ]
    
    for q in variantes:
        try:
            params = {
                'q': q,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'tn'   # Force la Tunisie — évite les faux positifs européens
            }
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, params=params, headers=headers, timeout=10, verify=False)
            time.sleep(1)  # Rate limit Nominatim
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data[0]['lat'])
                    lng = float(data[0]['lon'])
                    GEOCODE_CACHE[cache_key] = (lat, lng)
                    print(f"   \u2705 {nom_lieu} \u2192 ({lat:.6f}, {lng:.6f})")
                    return (lat, lng)
            elif response.status_code == 429:
                print(f"   \u26a0\ufe0f  Rate limit pour {nom_lieu}, pause...")
                time.sleep(5)
                
        except Exception as e:
            print(f"   \u274c Erreur pour {nom_lieu} ({q}): {e}")
            continue
            
    print(f"   \u26a0\ufe0f  Echec final pour: {nom_lieu}")
    return None


def distance_haversine_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))



def estimer_distance_fallback(lat1, lng1, lat2, lng2):
    """
    Estime la distance routiere (en km) quand OSRM est indisponible.
    Utilise le modele ML (Random Forest) si charge, sinon retombe sur
    le multiplicateur Haversine x1.3 (ancien comportement, garde comme
    filet de securite ultime si le modele lui-meme n'est pas charge).
 
    Retourne toujours un FLOAT en KILOMETRES.
    """
    dist_hav = distance_haversine_km(lat1, lng1, lat2, lng2)
 
    if MODEL_DISTANCE is not None:
        try:
            # Respecter EXACTEMENT l'ordre des features d'entrainement :
            # ['lat1', 'lng1', 'lat2', 'lng2', 'distance_haversine']
            X_pair = [[lat1, lng1, lat2, lng2, dist_hav]]
            pred_km = float(MODEL_DISTANCE.predict(X_pair)[0])
            # Garde-fou : une prediction ne devrait jamais etre inferieure
            # a la distance a vol d'oiseau (impossible physiquement), ni
            # demesurement plus grande (signe d'extrapolation hors zone
            # d'entrainement, ex: hors Grand Tunis). On bride dans une
            # plage raisonnable plutot que de faire confiance aveuglement
            # a une prediction hors-distribution.
            if pred_km < dist_hav:
                pred_km = dist_hav * 1.3  # incoherent -> repli sur l'ancien calcul
            elif pred_km > dist_hav * 3.0:
                pred_km = dist_hav * 1.3  # extrapolation suspecte -> repli
            return pred_km
        except Exception as e:
            print(f"[ML] Echec prediction distance, repli sur Haversine x1.3 : {e}")
 
    return dist_hav * 1.3


# ROUTES RÉELLES (OSRM)
def get_route_osrm(start, end):
    """Calcule route réelle entre 2 points via OSRM."""
    url = f"http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}"
    params = {'overview': 'full', 'geometries': 'geojson'}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok':
                route = data['routes'][0]
                return {
                    'distance_km': route['distance'] / 1000,
                    'duration_min': route['duration'] / 60,
                    'geometry': route['geometry']
                }
    except:
        pass
    # Fallback ML/Haversine si OSRM indisponible 
    # Vitesse moyenne unifiée à 40 km/h (dist * 1.5) pour correspondre avec optimiser_clusters_strategy
    dist = estimer_distance_fallback(start[0], start[1], end[0], end[1])
    return {'distance_km': dist, 'duration_min': dist * 1.5, 'geometry': None}

# PARAMÈTRES GLOBAUX CONFIGURABLES (modifiables via /api/update_params)

TARIFS = {
    'prise_en_charge': 0.900, 
    'prix_79m':        0.046,
    'prix_18s':        0.046,
    'coef_hp':         1.20,
    'coef_weekend':    1.15,
    'mode_actif':      'standard',   # standard | hp | we | hpwe
}

PARAMS_ALGO = {
    'max_cluster_distance_km': 5.0,
    'ortools_time_limit_s':  120,
    'direction_lambda':      2.0,
}

PARAMS_RSE = {
    'co2_kg_per_km':           0.12,   # source ADEME 2023
    'cout_individuel_per_km':  0.582,  # tarif taxi individuel de référence
}

def get_tarif_coef():
    mode = TARIFS.get('mode_actif', 'standard')
    coef = 1.0
    if mode in ('hp', 'hpwe'):   coef *= TARIFS.get('coef_hp', 1.20)
    if mode in ('we', 'hpwe'):   coef *= TARIFS.get('coef_weekend', 1.15)
    return coef

def calculer_tarif(distance_km, duree_min):
    """Tarif taxi tunisien avec coefficients configurables."""
    distance_m   = distance_km * 1000
    duree_s      = duree_min   * 60
    temps_arret  = duree_s     * 0.08

    base         = TARIFS.get('prise_en_charge', 0.900)
    cout_dist    = (distance_m  / 79) * TARIFS.get('prix_79m', 0.046)
    cout_temps   = (temps_arret / 18) * TARIFS.get('prix_18s', 0.046)
    total_base   = base + cout_dist + cout_temps

    coef         = get_tarif_coef()
    return {
        'base':        round(total_base, 3),
        'coefficient': round(coef, 4),
        'final':       round(total_base * coef, 3)
    }

def assigner_vehicules_ecologiques(vehicles_routes):
    """
    Assigne la flotte hétérogène aux trajets générés.
    Stratégie gloutonne : les véhicules les plus écologiques
    sont assignés aux trajets les plus longs.
    """
    sorted_routes = sorted(vehicles_routes, key=lambda x: x['distance_km'], reverse=True)
    fleet = PARAMS_RSE.get('fleet_composition', [])
    available_vehicles = []
    
    if not fleet or not isinstance(fleet, list):
        available_vehicles = [{'label': 'Berline', 'co2': 0.12, 'icon': '🚕'}] * len(vehicles_routes)
    else:
        for v in fleet:
            count = int(v.get('count', 0))
            if count > 0:
                available_vehicles.extend([v] * count)
        available_vehicles.sort(key=lambda x: float(x.get('co2', 0.12)))
        
    while len(available_vehicles) < len(vehicles_routes):
        available_vehicles.append({'label': 'Berline', 'co2': 0.12, 'icon': '🚕'})
        
    for i, route in enumerate(sorted_routes):
        route['vehicule'] = available_vehicles[i]

# OPTIMISATION MULTI-STRATÉGIES (OR-Tools, NN, Furthest)

def ordonner_ortools(cluster, destination):
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    import requests
    
    nodes = cluster + [destination]
    dest_idx = len(nodes) - 1
    matrix = None
    
    # API MATRIX OSRM : vraie distance routière (évite les erreurs liées aux obstacles géographiques)
    try:
        coords = ";".join([f"{n['lng']},{n['lat']}" for n in nodes])
        url = f"http://router.project-osrm.org/table/v1/driving/{coords}?annotations=distance"
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            matrix = resp.json().get('distances')
    except Exception:
        pass

    def get_dist(i, j):
        """Retourne la distance réelle (matrice OSRM) ou fallback ML/Haversine, en mètres."""
        if matrix and matrix[i] is not None and matrix[i][j] is not None:
            return int(matrix[i][j])  # mètres, depuis OSRM (vérité terrain)
        # Fallback ML si OSRM (table API) indisponible. estimer_distance_fallback
        # retourne des KM -> conversion en mètres pour rester cohérent avec le
        # reste de get_dist() qui travaille en mètres.
        n1, n2 = nodes[i], nodes[j]
        dist_km = estimer_distance_fallback(n1['lat'], n1['lng'], n2['lat'], n2['lng'])
        return int(dist_km * 1000)

    manager = pywrapcp.RoutingIndexManager(len(nodes), 1, dest_idx)
    routing = pywrapcp.RoutingModel(manager)
    
    def distance_callback(from_index, to_index):
        n1_idx = manager.IndexToNode(from_index)
        n2_idx = manager.IndexToNode(to_index)
        
        # OPEN VRP : Le "départ fictif" depuis destination coûte 0 → le solveur choisit librement le 1er arrêt
        if n1_idx == dest_idx:
            return 0
        return get_dist(n1_idx, n2_idx)
        
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Stratégie : PATH_CHEAPEST_ARC pour la solution initiale, puis amélioration locale 2-opt
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.SAVINGS
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = PARAMS_ALGO.get('ortools_time_limit_s', 30)
    
    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        ordered = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node_idx = manager.IndexToNode(index)
            if node_idx < len(cluster): ordered.append(nodes[node_idx])
            index = solution.Value(routing.NextVar(index))
        
        # Post-traitement 2-Opt : on vérifie si inverser l'ordre réduit la distance totale
        ordered = two_opt_improve(ordered, destination, get_dist, dest_idx)
        return ordered
    return cluster


def solve_vrp_ortools(employes, destination, capacites_flotte, time_limit_sec=30):
    """
    Solveur VRP avec OR-Tools + Dépôt Fictif (Dummy Node).
    
    Le Dépôt Fictif permet aux véhicules de "démarrer" virtuellement à coût 0,
    éliminant le biais qui forçait des zigzags pour éviter les trajets "à vide".
    Les véhicules terminent tous à la destination réelle.
    
    capacites_flotte : entier (capacité uniforme) ou liste (flotte hétérogène).
    """
    from ortools.constraint_solver import routing_enums_pb2, pywrapcp
    import requests

    n_employees = len(employes)

    # --- Construction de la liste de nœuds : employés + destination + dummy ---
    # nodes = [emp0, emp1, ..., empN-1, destination, dummy_start]
    nodes = employes + [destination]
    dest_idx = len(nodes) - 1       # index de la destination dans nodes
    dummy_idx = len(nodes)           # index du dépôt fictif (virtuel, pas dans nodes)
    total_nodes = len(nodes) + 1     # +1 pour le dummy

    # --- Normalisation : toujours travailler avec une liste de capacités ---
    if isinstance(capacites_flotte, int):
        capacites_vehicules = [capacites_flotte] * n_employees
    else:
        capacites_vehicules = list(capacites_flotte)
        while sum(capacites_vehicules) < n_employees:
            capacites_vehicules.append(1)

    max_vehicles = len(capacites_vehicules)

    # --- Matrice OSRM (ou fallback ML/Haversine) ---
    # On ne demande la matrice OSRM que pour les nœuds réels (employés + destination)
    dist_matrix = None
    try:
        coords = ";".join([f"{n['lng']},{n['lat']}" for n in nodes])
        url = f"http://router.project-osrm.org/table/v1/driving/{coords}?annotations=distance"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            dist_matrix = resp.json().get('distances')
    except Exception:
        pass

    def get_real_dist(i, j):
        """Distance entre deux nœuds réels (pas le dummy)."""
        if dist_matrix and i < len(dist_matrix) and j < len(dist_matrix):
            if dist_matrix[i] and dist_matrix[i][j] is not None:
                return int(dist_matrix[i][j])
        a, b = nodes[i], nodes[j]
        dist_km = estimer_distance_fallback(a['lat'], a['lng'], b['lat'], b['lng'])
        return int(dist_km * 1000)

    # --- Modèle OR-Tools avec Dépôt Fictif ---
    # Chaque véhicule PART du dummy_idx (coût 0) et ARRIVE à dest_idx
    starts = [dummy_idx] * max_vehicles
    ends = [dest_idx] * max_vehicles
    manager = pywrapcp.RoutingIndexManager(total_nodes, max_vehicles, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    def dist_callback(from_idx, to_idx):
        from_node = manager.IndexToNode(from_idx)
        to_node = manager.IndexToNode(to_idx)
        # Si on part du dummy, distance = 0 (le taxi "apparaît" chez le 1er employé)
        if from_node == dummy_idx:
            return 0
        # Si on va vers le dummy (ne devrait pas arriver, mais sécurité)
        if to_node == dummy_idx:
            return 0
        return get_real_dist(from_node, to_node)

    transit_cb = routing.RegisterTransitCallback(dist_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    # Coût fixe par véhicule : très petit (500m = 0.5 km) pour ne pas bloquer
    # l'ouverture de nouveaux taxis quand c'est nécessaire, mais suffisant
    # pour éviter d'ouvrir des taxis vides inutilement.
    COUT_FIXE_M = 500
    for v in range(max_vehicles):
        routing.SetFixedCostOfVehicle(COUT_FIXE_M, v)

    # --- Contrainte de capacité hétérogène ---
    def demand_callback(idx):
        node = manager.IndexToNode(idx)
        return 1 if node < n_employees else 0

    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb, 0, capacites_vehicules, True, "Capacity"
    )

    # --- Paramètres de recherche ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    # Temps de recherche généreux pour trouver le vrai minimum
    search_parameters.time_limit.seconds = max(30, time_limit_sec)

    # --- Résolution ---
    solution = routing.SolveWithParameters(search_parameters)
    if not solution:
        print("[VRP] OR-Tools n'a pas trouvé de solution.")
        return None

    # --- Extraction des routes ---
    routes = []
    for vehicle_id in range(max_vehicles):
        index = routing.Start(vehicle_id)
        route_nodes = []
        while not routing.IsEnd(index):
            node_idx = manager.IndexToNode(index)
            if node_idx < n_employees:
                route_nodes.append(employes[node_idx])
            index = solution.Value(routing.NextVar(index))
        
        if route_nodes:
            # L'algorithme VRP avec Dummy Depot trouve déjà l'ordre absolu optimal 
            # de la première prise en charge jusqu'à la destination.
            # Il ne faut SURTOUT PAS faire de rotation manuelle, sinon on détruit 
            # l'optimisation directionnelle (ex: forcer un demi-tour sur autoroute).
            routes.append(route_nodes)

    print(f"   [VRP] {len(routes)} véhicules utilisés sur {max_vehicles} disponibles.")
    return routes



def mesurer_dispersion_geographique(employes):
    """
    Ecart-type des distances de chaque employe au centroide du groupe,
    en km. Une valeur elevee indique des employes tres eparpilles
    geographiquement ; une valeur faible indique un groupe concentre.
    """
    if len(employes) <= 1:
        return 0.0
    lat_c = sum(e['lat'] for e in employes) / len(employes)
    lng_c = sum(e['lng'] for e in employes) / len(employes)
    distances = [
        distance_haversine_km(e['lat'], e['lng'], lat_c, lng_c)
        for e in employes
    ]
    moyenne = sum(distances) / len(distances)
    variance = sum((d - moyenne) ** 2 for d in distances) / len(distances)
    return math.sqrt(variance)
 
 

def construire_flotte_adaptative(employes, marge_securite=1.3):
    """
    Construit un pool de capacites ADAPTE a la dispersion geographique,
    en PARTANT du melange de base eprouve (construire_flotte_par_defaut)
    et en y AJOUTANT des petits taxis supplementaires si la dispersion
    est elevee - sans jamais retirer les gros taxis existants. Cela
    garantit que le solveur garde toutes ses options et ne peut donc
    jamais faire moins bien que le melange fixe seul (au pire, il
    ignore simplement les vehicules bonus s'ils ne sont pas utiles).
 
    Seuils de dispersion (ecart-type des distances au centroide, en km) :
      < 1.0 km   : pas de bonus, le melange de base suffit
      1.0-2.5 km : bonus modeste (quelques petits taxis en plus)
      > 2.5 km   : bonus plus consequent
    """
    n_employees = len(employes)
    dispersion = mesurer_dispersion_geographique(employes)
 
    pool_base = construire_flotte_par_defaut(n_employees, marge_securite)
 
    if dispersion < 1.0:
        bonus = []
    elif dispersion < 2.5:
        bonus = [2]  # un seul taxi bonus au lieu de 10% des employés
    else:
        bonus = [2, 2]  # deux taxis bonus max
    
    pool = pool_base + bonus
    pool.sort(reverse=True)
    return pool


def construire_flotte_par_defaut(n_employees, marge_securite=1.0):
    """
    Construit le pool MINIMAL de véhicules nécessaires.
    Avec capacité max 4, le minimum de véhicules = ceil(n/4).
    On ajoute un seul véhicule de surplus comme marge.
    """
    cap_max = 4
    n_min = math.ceil(n_employees / cap_max)
    n_vehicules = n_min + 1

    # Pool simple : tous à capacité max, le dernier à capacité variable
    pool = [cap_max] * n_vehicules
    pool.sort(reverse=True)
    return pool


def two_opt_improve(route, destination, get_dist_fn, dest_idx):
    """
    Amélioration 2-opt locale en post-traitement.
    Travaille directement sur les indices de la matrice pour comparer les coûts.
    route : liste de dicts d'employés (indices 0..n-1 dans la matrice)
    dest_idx : index de la destination dans la matrice (= len(cluster))
    """
    n = len(route)
    if n <= 2:
        return route

    # Ordre initial : [0, 1, 2, ..., n-1] → indices dans la matrice (= position dans `route`)
    best = list(range(n))

    def route_cost(order):
        cost = sum(get_dist_fn(order[i], order[i+1]) for i in range(len(order)-1))
        cost += get_dist_fn(order[-1], dest_idx)
        return cost

    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n):
                new_order = best[:i] + best[i:j+1][::-1] + best[j+1:]
                if route_cost(new_order) < route_cost(best):
                    best = new_order
                    improved = True
    
    return [route[idx] for idx in best]


def ordonner_direction_aware(cluster, destination):
    """
    Ordonnancement intelligent : progresse naturellement vers la destination.
    Commence par l'employe le plus loin, puis a chaque etape choisit le suivant
    qui minimise (distance_trajet + penalite_si_on_s_eloigne_de_la_destination).
    Evite les allers-retours comme la route orange.
    """
    if len(cluster) <= 1:
        return cluster.copy()

    def d(a, b):
        return distance_haversine_km(a['lat'], a['lng'], b['lat'], b['lng'])

    def d_dest(e):
        return distance_haversine_km(
            e['lat'], e['lng'],
            destination['lat'], destination['lng']
        )

    remaining = cluster.copy()

    # Toujours commencer par l'employe le plus loin de la destination
    remaining.sort(key=d_dest, reverse=True)
    ordered = [remaining.pop(0)]

    while remaining:
        current  = ordered[-1]
        d_curr   = d_dest(current)

        best_candidate = None
        best_score     = float('inf')

        for candidate in remaining:
            travel   = d(current, candidate)
            # Penalite si on s eloigne de la destination (facteur 2.0 calibre pour Tunis)
            lam = PARAMS_ALGO.get('direction_lambda', 2.0)
            backtrack = max(0.0, d_dest(candidate) - d_curr)
            score    = travel + lam * backtrack

            if score < best_score:
                best_score     = score
                best_candidate = candidate

        ordered.append(best_candidate)
        remaining.remove(best_candidate)

    # 2-Opt final pour supprimer les derniers croisements residuels
    ordered = two_opt_improve_route(ordered, destination, distance_haversine_km)
    return ordered


def optimiser_clusters_strategy(clusters, destination, strategy_name,
                                 employes, capacite,
                                 progress_callback=None, step_name='osrm'):

    vehicles_routes        = []
    total_distance_globale = 0
    total_duree_globale    = 0
    numero_vehicule        = 1

    # Notification de progression initiale
    if progress_callback:
        msg = ("OR-Tools en cours..."   if step_name == 'ortools'
               else "Nearest Neighbor..." if step_name == 'nn'
               else "Furthest First...")
        pct = 65 if step_name == 'ortools' else (75 if step_name == 'nn' else 85)
        progress_callback(step_name, pct, msg)

    total_osrm = sum(len(c) for c in clusters) * 2
    osrm_done  = 0

    # ═══════════════════════════════════════════════
    # BOUCLE PRINCIPALE : un cluster = un vehicule
    # ═══════════════════════════════════════════════
    for cluster in clusters:

        # ── Ordonnancement selon la strategie ──────
        if strategy_name == "Custom Manual Order":
            # L'utilisateur contrôle la COMPOSITION (qui est dans quel taxi).
            # On re-optimise automatiquement l'ORDRE de ramassage au sein de
            # chaque cluster via direction_aware + 2-opt, exactement comme
            # l'optimisation normale. Cela évite les zigzags et grands détours
            # causés par un simple swap manuel.
            ordered = cluster.copy()

        elif strategy_name == "Google OR-Tools (Recommandé)":
            # Direction-aware : progresse vers la destination sans detour
            ordered = ordonner_direction_aware(cluster, destination)

        elif strategy_name == "Nearest Neighbor":
            # Direction-aware identique : meme logique, clustering different
            ordered = ordonner_direction_aware(cluster, destination)

        else:
            # Furthest First : meme ordonnancement direction-aware
            # Le clustering FF a deja groupé les employes geographiquement disperses,
            # l ordonnancement direction-aware gere ensuite l ordre de passage optimal
            ordered = ordonner_direction_aware(cluster, destination)

                # ── Calcul des segments OSRM en UNE SEULE REQUÊTE par véhicule ───
        distance_route = 0.0
        duree_route    = 0.0
        segments       = []

        # Construire la chaîne de coordonnées: emp1;emp2;...;destination
        all_points = ordered + [destination]
        coords_str = ";".join([f"{p['lng']},{p['lat']}" for p in all_points])
        url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}"
        
        osrm_success = False
        try:
            response = requests.get(url, params={'overview': 'full', 'geometries': 'geojson'}, timeout=8)
            if response.status_code == 200:
                rdata = response.json()
                if rdata['code'] == 'Ok':
                    route = rdata['routes'][0]
                    osrm_success = True
                    legs = route['legs']
                    
                    # Iterer sur les "legs" (segments) retournés par OSRM
                    for i, leg in enumerate(legs):
                        prev = all_points[i]
                        curr = all_points[i+1]
                        
                        dist_km = leg['distance'] / 1000
                        dur_min = leg['duration'] / 60
                        
                        distance_route += dist_km
                        duree_route    += dur_min
                        segments.append({
                            'from':         prev['nom'],
                            'to':           curr['nom'],
                            'distance_km':  round(dist_km, 2),
                            'duree_min':    round(dur_min, 1)
                        })
        except Exception:
            pass

        # Fallback Haversine SI l'appel global OSRM a échoué
        if not osrm_success:
            for i in range(1, len(all_points)):
                prev = all_points[i-1]
                curr = all_points[i]
                dist_fb = distance_haversine_km(prev['lat'], prev['lng'], curr['lat'], curr['lng']) * 1.3
                dur_fb = dist_fb / (40 / 60.0)  # Fallback unifié à 40 km/h
                
                distance_route += dist_fb
                duree_route    += dur_fb
                segments.append({
                    'from':         prev['nom'],
                    'to':           curr['nom'],
                    'distance_km':  round(dist_fb, 2),
                    'duree_min':    round(dur_fb, 1)
                })

        # Mise à jour de la progression
        osrm_done += len(ordered)
        if progress_callback:
            pct_osrm = min(60, 25 + int(35 * osrm_done / total_osrm))
            progress_callback('osrm', pct_osrm, f"Calcul OSRM véhicule {numero_vehicule} terminé...")

        # ── Construction de l objet route ──────────
        tarif_route = calculer_tarif(distance_route, duree_route)
        waypoints   = (
            [[e['lat'], e['lng']] for e in ordered]
            + [[destination['lat'], destination['lng']]]
        )

        vehicles_routes.append({
            'vehicule_id':  f"Taxi {numero_vehicule} ({len(ordered)}/{capacite} places)",
            'ordre':        ordered,
            'segments':     segments,
            'distance_km':  round(distance_route, 2),
            'duree_min':    round(duree_route,    1),
            'tarif':        tarif_route,
            'waypoints':    waypoints
        })

        total_distance_globale += distance_route
        total_duree_globale    += duree_route
        numero_vehicule        += 1

    # ═══════════════════════════════════════════════
    # AGREGATS FINANCIERS ET RSE
    # ═══════════════════════════════════════════════
    tarif_global_final = round(sum(r['tarif']['final'] for r in vehicles_routes), 2)
    tarif_global = {
        'base':        round(sum(r['tarif']['base'] for r in vehicles_routes), 2),
        'coefficient': 1.0,
        'final':       tarif_global_final
    }

    # Cout hypothetique : chaque employe prendrait un taxi individuel
    cout_perso_total      = 0.0
    distance_perso_totale = 0.0

    for e in employes:
        dist_ind  = distance_haversine_km(
            e['lat'], e['lng'], destination['lat'], destination['lng']
        ) * 1.3
        duree_ind = dist_ind / (40 / 60.0)
        tarif_ind = calculer_tarif(dist_ind, duree_ind)
        cout_perso_total      += tarif_ind['final']
        distance_perso_totale += dist_ind

    co2_kg_km    = PARAMS_RSE.get('co2_kg_per_km', 0.12)
    co2_perso_kg = distance_perso_totale  * co2_kg_km
    co2_taxi_kg  = total_distance_globale * co2_kg_km
    
    # Sécurisation du calcul du taux de remplissage si capacite est une liste ou 'ia'
    cap_for_calc = capacite
    if isinstance(cap_for_calc, list):
        cap_for_calc = max(cap_for_calc) if cap_for_calc else 1
    elif not isinstance(cap_for_calc, (int, float)):
        cap_for_calc = 4  # Fallback par défaut
        
    taux_remplissage = (
        min(100.0, (len(employes) / (len(vehicles_routes) * cap_for_calc)) * 100)
        if vehicles_routes else 0
    )


    rse_metrics = {
        'distance_saved_km':    round(max(0, distance_perso_totale  - total_distance_globale), 2),
        'co2_saved_kg':         round(max(0, co2_perso_kg           - co2_taxi_kg),            2),
        'cost_saved_tnd':       round(max(0, cout_perso_total       - tarif_global['final']),  2),
        'fill_rate_percent':    round(taux_remplissage, 1),
        'co2_scenario_perso':   round(co2_perso_kg,    2),
        'co2_scenario_moovly':  round(co2_taxi_kg,     2),
        'cost_scenario_perso':  round(cout_perso_total, 2)
    }

    return {
        'methode':      strategy_name,
        'is_best':      False,
        'destination':  destination,
        'routes':       vehicles_routes,
        'distance_km':  round(total_distance_globale, 2),
        'duree_min':    round(total_duree_globale,    1),
        'tarif':        tarif_global,
        'rse_metrics':  rse_metrics
    }
def two_opt_improve_route(route, destination, dist_func):
    """Amélioration 2-Opt pour une liste ordonnée d'employés."""
    n = len(route)
    if n <= 2:
        return route
    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(n-1):
            for j in range(i+2, n):
                new_route = best[:i] + best[i:j+1][::-1] + best[j+1:]
                # Coût total = somme distances entre employés + dernier employé -> destination
                cost_old = sum(dist_func(best[k]['lat'], best[k]['lng'], best[k+1]['lat'], best[k+1]['lng']) for k in range(n-1))
                cost_old += dist_func(best[-1]['lat'], best[-1]['lng'], destination['lat'], destination['lng'])
                cost_new = sum(dist_func(new_route[k]['lat'], new_route[k]['lng'], new_route[k+1]['lat'], new_route[k+1]['lng']) for k in range(n-1))
                cost_new += dist_func(new_route[-1]['lat'], new_route[-1]['lng'], destination['lat'], destination['lng'])
                if cost_new < cost_old:
                    best = new_route
                    improved = True
                    break
            if improved:
                break
    return best


def suggerer_capacite_optimale(employes, destination, capacites=[1,2,3,4], critere='distance'):
    """
    Lance le VRP pour chaque capacité et retourne la meilleure selon le critère.
    Utilise la distance Haversine (rapide) pour comparer les capacités sans 
    surcharger l'API OSRM.
    """
    best_cap = None
    best_value = float('inf')
    results = {}
    
    for cap in capacites:
        # On utilise un time_limit court car c'est juste pour comparer
        routes = solve_vrp_ortools(employes, destination, cap, time_limit_sec=15)
        if not routes:
            continue
            
        # Calculer la distance totale (Haversine) pour cette capacité
        total_dist = 0.0
        for route in routes:
            if not route:
                continue
            # Distance entre les employés du cluster
            for i in range(len(route) - 1):
                total_dist += distance_haversine_km(
                    route[i]['lat'], route[i]['lng'],
                    route[i+1]['lat'], route[i+1]['lng']
                )
            # Dernier employé -> destination
            total_dist += distance_haversine_km(
                route[-1]['lat'], route[-1]['lng'],
                destination['lat'], destination['lng']
            )
            
        results[cap] = round(total_dist, 2)
        if total_dist < best_value:
            best_value = total_dist
            best_cap = cap
            
    return best_cap, results



def cluster_by_proximity(employes, destination, capacite, max_detour_ratio=0.3, max_cluster_distance_km=5.0):
    """
    Clusterisation intelligente : regroupe uniquement les employés très proches.
    
    Args:
        max_detour_ratio: augmentation maximale autorisée de la distance totale du cluster
                          par rapport à la somme des distances directes (ex: 0.3 = +30%)
        max_cluster_distance_km: distance maximale entre deux employés du même cluster (km)
    """
    from math import inf

    if not employes:
        return []

    # Pré-calculer toutes les distances entre employés (Haversine, rapide)
    n = len(employes)
    dist_matrix = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            d = distance_haversine_km(employes[i]['lat'], employes[i]['lng'],
                                      employes[j]['lat'], employes[j]['lng'])
            dist_matrix[i][j] = d
            dist_matrix[j][i] = d

    # Distance de chaque employé à la destination
    dist_to_dest = [distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng'])
                    for e in employes]

    # Trier les employés par distance à la destination (du plus proche au plus loin)
    sorted_indices = sorted(range(n), key=lambda i: dist_to_dest[i], reverse=True)

    assigned = [False] * n
    clusters = []

    for idx in sorted_indices:
        if assigned[idx]:
            continue

        # Créer un nouveau cluster avec cet employé
        cluster = [idx]
        assigned[idx] = True
        current_dist_sum = dist_to_dest[idx]  # distance directe de ce seul employé

        # Essayer d'ajouter d'autres employés non assignés, par ordre de proximité
        # On limite la taille à capacite
        while len(cluster) < capacite:
            # Chercher le candidat le plus proche de n'importe quel membre du cluster
            best_candidate = -1
            best_min_dist = inf
            for j in range(n):
                if assigned[j]:
                    continue
                # distance minimale entre j et n'importe quel membre du cluster
                min_d = min(dist_matrix[j][m] for m in cluster)
                if min_d < best_min_dist:
                    best_min_dist = min_d
                    best_candidate = j

            if best_candidate == -1:
                break  # plus aucun candidat

            # Vérifier si l'ajout de ce candidat respecte les contraintes
            # Distance entre candidat et son plus proche voisin dans le cluster
            if best_min_dist > max_cluster_distance_km:
                break  # trop loin, on arrête d'agrandir ce cluster

            # Mesure plus réaliste : le détour supplémentaire pour aller chercher ce candidat
            # On calcule grossièrement la distance supplémentaire = 2 * best_min_dist
            # (car il faut un aller-retour depuis le cluster)
            detour_estime = 2 * best_min_dist
            distance_total_estimee = current_dist_sum + dist_to_dest[best_candidate]

            # Si le détour dépasse le ratio autorisé par rapport à la distance totale, on l'ignore
            # Ex: max_detour_ratio = 0.3 -> on n'accepte pas un détour qui fait +30% du trajet total
            if distance_total_estimee > 0 and (detour_estime / distance_total_estimee) > max_detour_ratio:
                break  # Détour trop important, on arrête d'agrandir ce cluster

            # Accepter le candidat
            cluster.append(best_candidate)
            assigned[best_candidate] = True
            current_dist_sum = distance_total_estimee

        # Convertir les indices en objets employés
        clusters.append([employes[i] for i in cluster])

    return clusters




# GÉNÉRATION DE SUGGESTIONS MULTIPLES

def normaliser_et_calculer_scores(suggestions, poids: dict):
    """
    Normalise les métriques (distance, coût, CO2) sur une échelle 0-1 
    avant d'appliquer les poids. Cela empêche le coût (qui a une grande 
    valeur numérique) de dominer le score final.
    """
    if not suggestions:
        return []

    # 1. Trouver les valeurs maximales de ce lot de suggestions
    max_dist = max((s['distance_km'] for s in suggestions), default=1.0) or 1.0
    max_cout = max((s['tarif']['final'] for s in suggestions), default=1.0) or 1.0
    max_co2  = max((s.get('rse_metrics', {}).get('co2_scenario_moovly', 0) for s in suggestions), default=1.0) or 1.0

    # 2. Calculer le score normalisé pour chaque suggestion
    for s in suggestions:
        rse = s.get('rse_metrics', {})
        
        # Normalisation (0 = meilleur, 1 = pire)
        dist_norm = s['distance_km'] / max_dist
        cout_norm = s['tarif']['final'] / max_cout
        co2_norm  = rse.get('co2_scenario_moovly', 0) / max_co2

        # Score composite pondéré
        s['score_composite'] = round(
            poids.get('distance', 0.33) * dist_norm +
            poids.get('cout', 0.33) * cout_norm +
            poids.get('co2', 0.34) * co2_norm,
            4
        )

    # 3. Trier par le nouveau score (le plus bas = le meilleur)
    suggestions.sort(key=lambda x: x['score_composite'])
    
    # 4. Marquer le meilleur comme étant le meilleur
    if suggestions:
        suggestions[0]['is_best'] = True
        
    return suggestions

def generer_suggestions_manual(manual_cluster_ids, destination, employes_pool, capacite=3, poids=None, progress_callback=None):
    if poids is None:
        poids = {'distance': 0.33, 'cout': 0.33, 'co2': 0.34}
        
    print("\n" + "🔷"*40)
    print(f"🔧 OPTIMISATION MANUELLE (Clusters pré-définis)")
    print("🔷"*40)

    emp_by_id = {e['_id']: e for e in employes_pool}
    clusters = []
    for id_list in manual_cluster_ids:
        cluster = [emp_by_id[eid] for eid in id_list if eid in emp_by_id]
        if cluster:
            clusters.append(cluster)

    all_employes = [e for c in clusters for e in c]
    suggestions = []
    strategies = ["Custom Manual Order"]

    for strt in strategies:
        print(f"\n🚀 Solver Manuel: {strt}")
        sug = optimiser_clusters_strategy(clusters, destination, strt, all_employes, capacite, progress_callback, 'ortools')
        suggestions.append(sug)

    # Utilisation du nouveau calcul normalisé
    return normaliser_et_calculer_scores(suggestions, poids)

def cluster_kmeans(employes, destination, capacite):
    """
    🧠 Clustering intelligent par zones géographiques (K-Means ML).
    
    Approche "Cluster-First, Route-Second" :
    1. K-Means identifie automatiquement les zones géographiques naturelles
    2. Les employés d'une même zone sont TOUJOURS dans le même véhicule
    3. Rééquilibrage pour respecter la contrainte de capacité
    
    Avantage vs Greedy : ne sépare jamais des employés proches dans 2 taxis différents.
    """
    from sklearn.cluster import KMeans
    
    n = len(employes)
    k = math.ceil(n / capacite)
    
    if k <= 1:
        return [employes.copy()]
    
    # ── Matrice de coordonnées GPS ──
    coords = np.array([[e['lat'], e['lng']] for e in employes])
    
    # ── K-Means : trouver exactement k zones géographiques naturelles ──
    # On utilise exactement k véhicules pour forcer la densification
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
    labels = kmeans.fit_predict(coords)
    
    # Grouper par label
    raw = {}
    for i, label in enumerate(labels):
        raw.setdefault(int(label), []).append(employes[i])
    
    trial_clusters = list(raw.values())
    
    # ── Rééquilibrage : respecter la capacité max par cluster ──
    changed = True
    max_iter = 100
    it = 0
    while changed and it < max_iter:
        changed = False
        it += 1
        for ci in range(len(trial_clusters)):
            while len(trial_clusters[ci]) > capacite:
                # Retirer l'employé le plus éloigné du centre de CE cluster
                center_lat = sum(e['lat'] for e in trial_clusters[ci]) / len(trial_clusters[ci])
                center_lng = sum(e['lng'] for e in trial_clusters[ci]) / len(trial_clusters[ci])
                trial_clusters[ci].sort(key=lambda e: distance_haversine_km(e['lat'], e['lng'], center_lat, center_lng))
                overflow = trial_clusters[ci].pop()  # le plus éloigné du centre
                
                # Trouver le cluster le plus proche avec de la place
                best_j = None
                best_d = float('inf')
                for cj in range(len(trial_clusters)):
                    if cj != ci and len(trial_clusters[cj]) < capacite:
                        cj_lat = sum(e['lat'] for e in trial_clusters[cj]) / len(trial_clusters[cj])
                        cj_lng = sum(e['lng'] for e in trial_clusters[cj]) / len(trial_clusters[cj])
                        d = distance_haversine_km(overflow['lat'], overflow['lng'], cj_lat, cj_lng)
                        if d < best_d:
                            best_d = d
                            best_j = cj
                
                if best_j is not None:
                    trial_clusters[best_j].append(overflow)
                    changed = True
                else:
                    # Pas de place → créer un nouveau cluster (ne devrait pas arriver si k=ceil(n/cap))
                    trial_clusters.append([overflow])
                    changed = True
                    break
    
    # Nettoyer les clusters vides
    best_clusters = [c for c in trial_clusters if c]
    
    print(f"   🧠 K-Means → {len(best_clusters)} clusters générés")
    for ci, cl in enumerate(best_clusters):
        print(f"      Cluster {ci+1}: {[e.get('nom','?') for e in cl]}")
    
    return best_clusters

'''
def cluster_greedy(employes, destination, capacite):
    """
    Clustering heuristique : seed = plus loin, puis minimisation du détour.
    """
    clusters = []
    unassigned = employes.copy()
    while unassigned:
        unassigned.sort(key=lambda e: distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']), reverse=True)
        seed = unassigned.pop(0)
        cluster = [seed]
        
        while len(cluster) < capacite and unassigned:
            last = cluster[-1]
            unassigned.sort(key=lambda e: distance_haversine_km(last['lat'], last['lng'], e['lat'], e['lng']) + 
                                          distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']))
            cluster.append(unassigned.pop(0))
        clusters.append(cluster)
    return clusters
'''
    
def cluster_nearest_neighbor(employes, destination, capacite):
    clusters = []
    unassigned = employes.copy()
    while unassigned:
        unassigned.sort(key=lambda e: distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']), reverse=True)
        seed = unassigned.pop(0)
        cluster = [seed]
        while len(cluster) < capacite and unassigned:
            last = cluster[-1]
            unassigned.sort(key=lambda e: distance_haversine_km(last['lat'], last['lng'], e['lat'], e['lng']) + 
                                          distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']))
            cluster.append(unassigned.pop(0))
        clusters.append(cluster)
    return clusters

def cluster_furthest_first(employes, destination, capacite):
    clusters = []
    unassigned = employes.copy()
    while unassigned:
        unassigned.sort(key=lambda e: distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']), reverse=True)
        seed = unassigned.pop(0)
        cluster = [seed]
        while len(cluster) < capacite and unassigned:
            unassigned.sort(key=lambda e: min(distance_haversine_km(e['lat'], e['lng'], c['lat'], c['lng']) for c in cluster), reverse=True)
            cluster.append(unassigned.pop(0))
        clusters.append(cluster)
    return clusters

def generer_suggestions(employes, destination, capacite=3, poids=None, progress_callback=None):
    if poids is None:
        poids = {'distance': 0.33, 'cout': 0.33, 'co2': 0.34}

    if not employes:
        return []

    # --- Construction du pool de véhicules ---
    if isinstance(capacite, str) and capacite.lower() == 'ia':
        # Mode IA : le modèle décide de la flotte
        flotte_pool = predire_flotte_ia(employes, destination)
        cap_cluster = int(flotte_pool[0]) if flotte_pool else 4
    elif isinstance(capacite, (list, tuple)):
        flotte_pool = list(capacite)
        cap_cluster = int(max(flotte_pool))
    else:
        # Mode fixe : construire un pool de véhicules TOUS à cette capacité
        cap_fixe = int(capacite)
        n_min = math.ceil(len(employes) / cap_fixe)
        flotte_pool = [cap_fixe] * (n_min + 1)  # +1 de marge
        cap_cluster = cap_fixe

    print(f"* GÉNÉRATION (cap={capacite} | pool={flotte_pool[:5]}...{len(flotte_pool)} véhicules)")

    if progress_callback:
        progress_callback('init', 5, 'Préparation des données...')

    STRATEGIES = [
        {
            "name": "Google OR-Tools (Recommandé)",
            "clustering_method": "VRP global (OR-Tools)",
            "step": "ortools",
            "use_full_vrp": True
        },
        {
            "name": "Nearest Neighbor",
            "cluster": cluster_nearest_neighbor,
            "clustering_method": "Chaîne (proche en proche)",
            "step": "nn"
        },
        {
            "name": "Furthest First",
            "cluster": cluster_furthest_first,
            "clustering_method": "Dispersion maximale",
            "step": "furthest"
        },
    ]

    suggestions = []

    for strt in STRATEGIES:
        if progress_callback:
            progress_callback('clustering', 15, f"Préparation ({strt['name']})...")
        print(f"\n Exécution solver: {strt['name']}")

        if strt.get('use_full_vrp'):
            routes_vrp = solve_vrp_ortools(employes, destination, flotte_pool, time_limit_sec=60)
            if routes_vrp is None:
                print(f"   ⚠️ OR-Tools n'a pas trouvé de solution.")
                continue
            sug = build_suggestion_from_routes(routes_vrp, destination, employes, flotte_pool, strt['name'])
            sug['clustering_method'] = strt['clustering_method']
        else:
            clusters = strt["cluster"](employes, destination, cap_cluster)
            sug = optimiser_clusters_strategy(clusters, destination, strt['name'], employes, cap_cluster, progress_callback, strt['step'])
            sug['clustering_method'] = strt['clustering_method']

        # On n'applique plus le score ici, on le fera à la fin sur toutes les suggestions
        suggestions.append(sug)

    if progress_callback:
        progress_callback('rse', 92, 'Calcul métriques RSE...')

    if not suggestions:
        return []

    return normaliser_et_calculer_scores(suggestions, poids)


def build_suggestion_from_routes(routes_ordered, destination, all_employes, capacite, method_name):
    """
    Construit une suggestion (même format que optimiser_clusters_strategy)
    à partir d'une liste de routes déjà ordonnées.
    """
    vehicles_routes = []
    total_distance = 0.0
    total_duree = 0.0
    numero = 1

    for ordre in routes_ordered:
        distance_route = 0.0
        duree_route = 0.0
        segments = []
        waypoints = []

        # Segments entre employés successifs
        for i in range(1, len(ordre)):
            prev = ordre[i-1]
            curr = ordre[i]
            rd = get_route_osrm((prev['lat'], prev['lng']), (curr['lat'], curr['lng']))
            if not rd:
                rd = {'distance_km': distance_haversine_km(prev['lat'], prev['lng'], curr['lat'], curr['lng']) * 1.3, 'duration_min': 2}
            distance_route += rd['distance_km']
            duree_route += rd['duration_min']
            segments.append({'from': prev['nom'], 'to': curr['nom'], 'distance_km': round(rd['distance_km'],2), 'duree_min': round(rd['duration_min'],1)})
            waypoints.append([prev['lat'], prev['lng']])

        # Dernier segment vers la destination
        last = ordre[-1]
        rd = get_route_osrm((last['lat'], last['lng']), (destination['lat'], destination['lng']))
        if not rd:
            rd = {'distance_km': distance_haversine_km(last['lat'], last['lng'], destination['lat'], destination['lng']) * 1.3, 'duration_min': 2}
        distance_route += rd['distance_km']
        duree_route += rd['duration_min']
        segments.append({'from': last['nom'], 'to': destination['nom'], 'distance_km': round(rd['distance_km'],2), 'duree_min': round(rd['duration_min'],1)})
        waypoints.append([last['lat'], last['lng']])
        waypoints.append([destination['lat'], destination['lng']])

        tarif_route = calculer_tarif(distance_route, duree_route)

        cap_label = max(capacite) if isinstance(capacite, (list, tuple)) else int(capacite)
        vehicles_routes.append({
            'vehicule_id': f"Taxi {numero} ({len(ordre)}/{cap_label} places)",
            'ordre': ordre,
            'segments': segments,
            'distance_km': round(distance_route, 2),
            'duree_min': round(duree_route, 1),
            'tarif': tarif_route,
            'waypoints': waypoints
        })
        total_distance += distance_route
        total_duree += duree_route
        numero += 1

    # Métriques RSE
    assigner_vehicules_ecologiques(vehicles_routes)
    
    total_distance_km = total_distance
    total_duree_min = total_duree
    tarif_global_final = sum(r['tarif']['final'] for r in vehicles_routes)
    tarif_global = {'base': sum(r['tarif']['base'] for r in vehicles_routes), 'coefficient': 1.0, 'final': tarif_global_final}

    cout_perso_total = 0.0
    distance_perso = 0.0
    for e in all_employes:
        d = distance_haversine_km(e['lat'], e['lng'], destination['lat'], destination['lng']) * 1.3
        distance_perso += d
        cout_perso_total += calculer_tarif(d, d / (40 / 60.0))['final']
        
    co2_taxi = sum(r['distance_km'] * float(r['vehicule'].get('co2', 0.12)) for r in vehicles_routes)
    co2_perso = distance_perso * PARAMS_RSE.get('co2_kg_per_km', 0.12)

    capacity_value = None
    if isinstance(capacite, (list, tuple)) and capacite:
        capacity_value = max(capacite)
    else:
        capacity_value = int(capacite)

    taux_remplissage = (len(all_employes) / (len(vehicles_routes) * capacity_value)) * 100 if vehicles_routes and capacity_value else 0

    rse_metrics = {
        'distance_saved_km': round(max(0, distance_perso - total_distance_km), 2),
        'co2_saved_kg': round(max(0, co2_perso - co2_taxi), 2),
        'cost_saved_tnd': round(max(0, cout_perso_total - tarif_global['final']), 2),
        'fill_rate_percent': round(taux_remplissage, 1),
        'co2_scenario_perso': round(co2_perso, 2),
        'co2_scenario_moovly': round(co2_taxi, 2),
        'cost_scenario_perso': round(cout_perso_total, 2)
    }

    return {
        'methode': method_name,
        'is_best': False,
        'destination': destination,
        'routes': vehicles_routes,
        'distance_km': round(total_distance_km, 2),
        'duree_min': round(total_duree_min, 1),
        'tarif': tarif_global,
        'rse_metrics': rse_metrics,
        'clustering_method': 'VRP global (OR-Tools)',
        'score_composite': 0.0
    }

        


