"""
benchmark_flotte_heterogene.py
================================
Compare la flotte heterogene (melange de taxis 1-4 places, construit par
construire_flotte_par_defaut) face a la capacite uniforme actuelle
(meme capacite pour tous les taxis), sur les memes scenarios.

Ce qu'on mesure :
  - Distance totale (km) : l'objectif principal du VRP
  - Nombre de vehicules reellement utilises : le cout reel pour Moovly
    (chaque taxi = une prise en charge + un chauffeur, independamment
    du nombre de km parcourus)

Si la flotte heterogene gagne sur l'un ou l'autre (idealement les deux),
c'est une amelioration mesurable, independante de tout ML - la base sur
laquelle le futur modele ML viendra s'appuyer.

A placer dans le meme dossier que moovly_system.py.
Usage:
    python benchmark_flotte_heterogene.py
"""
import sys
import os
import time
import random
import statistics

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import moovly_system as ms

DESTINATION = {'nom': 'Bureau Moovly', 'lat': 36.8065, 'lng': 10.1815, '_id': 'dest_bureau'}


def generer_employes(n, seed=None):
    if seed is not None:
        random.seed(seed)
    employes = []
    for i in range(n):
        lat = DESTINATION['lat'] + random.uniform(-0.08, 0.08)
        lng = DESTINATION['lng'] + random.uniform(-0.08, 0.08)
        employes.append({
            'id': f'E{i}', 'nom': f'Employe_{i}',
            'lat': lat, 'lng': lng, '_id': f'emp_{i}'
        })
    return employes


def route_total_distance_haversine(routes, destination):
    total = 0.0
    for route in routes:
        pts = route + [destination]
        for i in range(len(pts) - 1):
            total += ms.distance_haversine_km(
                pts[i]['lat'], pts[i]['lng'], pts[i + 1]['lat'], pts[i + 1]['lng']
            )
    return total


def run_trial(employes, capacite_ou_pool, time_limit_s):
    t0 = time.perf_counter()
    routes = ms.solve_vrp_ortools(employes, DESTINATION, capacite_ou_pool, time_limit_sec=time_limit_s)
    elapsed = time.perf_counter() - t0
    if not routes:
        return None
    cost = route_total_distance_haversine(routes, DESTINATION)
    n_vehicules_utilises = len(routes)
    return {'time_s': elapsed, 'cost_km': cost, 'n_vehicules': n_vehicules_utilises}


def main():
    print("=" * 70)
    print("BENCHMARK : Flotte hétérogène (1-4 places) vs capacité uniforme")
    print("=" * 70)

    # Capacite uniforme de reference : on teste contre 3 ET 4, car le
    # "meilleur" choix uniforme depend du scenario - on veut etre honnete
    # et comparer contre le meilleur des deux, pas le plus faible des deux.
    configs = [
        {'n_employes': 15, 'time_limit_s': 5},
        {'n_employes': 25, 'time_limit_s': 5},
        {'n_employes': 35, 'time_limit_s': 5},
        {'n_employes': 50, 'time_limit_s': 8},
    ]
    n_seeds = 8

    for cfg in configs:
        n = cfg['n_employes']
        tl = cfg['time_limit_s']
        print(f"\n--- n={n} employés, time_limit={tl}s, {n_seeds} essais ---")

        pool = ms.construire_flotte_par_defaut(n)
        print(f"Pool hétérogène utilisé : {pool} ({sum(pool)} places, {len(pool)} taxis dispo)")

        costs_hetero, costs_cap3, costs_cap4 = [], [], []
        nveh_hetero, nveh_cap3, nveh_cap4 = [], [], []

        for seed in range(n_seeds):
            employes = generer_employes(n, seed=seed)

            r_hetero = run_trial(employes, pool, tl)
            r_cap3 = run_trial(employes, 3, tl)
            r_cap4 = run_trial(employes, 4, tl)

            if r_hetero:
                costs_hetero.append(r_hetero['cost_km'])
                nveh_hetero.append(r_hetero['n_vehicules'])
            if r_cap3:
                costs_cap3.append(r_cap3['cost_km'])
                nveh_cap3.append(r_cap3['n_vehicules'])
            if r_cap4:
                costs_cap4.append(r_cap4['cost_km'])
                nveh_cap4.append(r_cap4['n_vehicules'])

        if not costs_hetero:
            print("  Aucun essai valide pour la flotte hétérogène.")
            continue

        print(f"\n  {'Stratégie':<25} {'Distance moy (km)':>20} {'Taxis utilisés (moy)':>22}")
        print(f"  {'-'*25} {'-'*20} {'-'*22}")
        print(f"  {'Flotte hétérogène':<25} {statistics.mean(costs_hetero):>20.2f} {statistics.mean(nveh_hetero):>22.1f}")
        if costs_cap3:
            print(f"  {'Capacité uniforme = 3':<25} {statistics.mean(costs_cap3):>20.2f} {statistics.mean(nveh_cap3):>22.1f}")
        if costs_cap4:
            print(f"  {'Capacité uniforme = 4':<25} {statistics.mean(costs_cap4):>20.2f} {statistics.mean(nveh_cap4):>22.1f}")

        # Comparaison contre le MEILLEUR des deux uniformes (honnete : pas
        # contre le plus faible, sinon le resultat serait artificiellement flatteur)
        meilleur_uniforme_cost = min(
            statistics.mean(costs_cap3) if costs_cap3 else float('inf'),
            statistics.mean(costs_cap4) if costs_cap4 else float('inf')
        )
        gain_distance = (meilleur_uniforme_cost - statistics.mean(costs_hetero)) / meilleur_uniforme_cost * 100
        print(f"\n  -> Gain distance hétérogène vs meilleur uniforme : {gain_distance:+.1f}%")

    print("\n" + "=" * 70)
    print("INTERPRETATION :")
    print("  - Gain distance > 0 ET/OU moins de taxis utilisés : la flotte")
    print("    hétérogène apporte une vraie amélioration mesurable.")
    print("  - Gain nul ou négatif : à documenter honnêtement, comme pour")
    print("    le warm-start - ne pas forcer une conclusion positive.")
    print("=" * 70)


if __name__ == '__main__':
    main()