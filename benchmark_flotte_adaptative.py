"""
benchmark_flotte_adaptative.py
================================
Compare 3 strategies de composition de flotte, sur des scenarios a
DISPERSION GEOGRAPHIQUE VARIABLE (pas juste taille variable comme avant) :

  1. Capacite uniforme (meilleure des deux, 3 ou 4) - la baseline historique
  2. Flotte heterogene a melange FIXE (construire_flotte_par_defaut)
  3. Flotte heterogene a melange ADAPTATIF (construire_flotte_adaptative)

L'INTERET de ce benchmark : generer des scenarios avec des dispersions
TRES DIFFERENTES (employes concentres vs employes eparpilles) pour voir
si l'adaptation a la geographie reelle (3) bat le melange fixe (2) -
PRECISEMENT la question qu'on doit trancher avant de songer a entrainer
un modele ML par-dessus.

A placer dans le meme dossier que moovly_system.py.
Usage:
    python benchmark_flotte_adaptative.py
"""
import sys
import os
import time
import random
import statistics

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import moovly_system as ms

DESTINATION = {'nom': 'Bureau Moovly', 'lat': 36.8065, 'lng': 10.1815, '_id': 'dest_bureau'}


def generer_employes(n, spread, seed=None):
    """spread controle la dispersion geographique (degres lat/lng)."""
    if seed is not None:
        random.seed(seed)
    employes = []
    for i in range(n):
        lat = DESTINATION['lat'] + random.uniform(-spread, spread)
        lng = DESTINATION['lng'] + random.uniform(-spread, spread)
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
    routes = ms.solve_vrp_ortools(employes, DESTINATION, capacite_ou_pool, time_limit_sec=time_limit_s)
    if not routes:
        return None
    cost = route_total_distance_haversine(routes, DESTINATION)
    return {'cost_km': cost, 'n_vehicules': len(routes)}


def main():
    print("=" * 70)
    print("BENCHMARK : Mélange FIXE vs Mélange ADAPTATIF (dispersion)")
    print("=" * 70)

    # Scenarios a dispersion VARIABLE (le facteur qu'on teste), taille fixe
    # a 25 employes pour isoler l'effet de la dispersion seule.
    scenarios = [
        {'label': 'Concentré (employés proches)', 'n': 25, 'spread': 0.02, 'tl': 5},
        {'label': 'Dispersion normale', 'n': 25, 'spread': 0.08, 'tl': 5},
        {'label': 'Très dispersé', 'n': 25, 'spread': 0.15, 'tl': 5},
    ]
    n_seeds = 8

    for sc in scenarios:
        print(f"\n--- {sc['label']} (n={sc['n']}, spread={sc['spread']}) ---")

        costs_uniforme, costs_fixe, costs_adaptatif = [], [], []
        nveh_uniforme, nveh_fixe, nveh_adaptatif = [], [], []
        dispersions = []

        for seed in range(n_seeds):
            employes = generer_employes(sc['n'], sc['spread'], seed=seed)
            dispersions.append(ms.mesurer_dispersion_geographique(employes))

            pool_fixe = ms.construire_flotte_par_defaut(sc['n'])
            pool_adaptatif = ms.construire_flotte_adaptative(employes)  # v2 : additive

            r_cap3 = run_trial(employes, 3, sc['tl'])
            r_cap4 = run_trial(employes, 4, sc['tl'])
            r_fixe = run_trial(employes, pool_fixe, sc['tl'])
            r_adapt = run_trial(employes, pool_adaptatif, sc['tl'])

            if r_cap3 and r_cap4:
                meilleur_uniforme = r_cap3 if r_cap3['cost_km'] < r_cap4['cost_km'] else r_cap4
                costs_uniforme.append(meilleur_uniforme['cost_km'])
                nveh_uniforme.append(meilleur_uniforme['n_vehicules'])
            if r_fixe:
                costs_fixe.append(r_fixe['cost_km'])
                nveh_fixe.append(r_fixe['n_vehicules'])
            if r_adapt:
                costs_adaptatif.append(r_adapt['cost_km'])
                nveh_adaptatif.append(r_adapt['n_vehicules'])

        print(f"Dispersion géographique mesurée (moy.) : {statistics.mean(dispersions):.2f} km")
        print(f"\n  {'Stratégie':<30} {'Distance moy (km)':>18} {'Taxis (moy)':>14}")
        print(f"  {'-'*30} {'-'*18} {'-'*14}")
        if costs_uniforme:
            print(f"  {'Capacité uniforme (meilleur)':<30} {statistics.mean(costs_uniforme):>18.2f} {statistics.mean(nveh_uniforme):>14.1f}")
        if costs_fixe:
            print(f"  {'Flotte mélange FIXE':<30} {statistics.mean(costs_fixe):>18.2f} {statistics.mean(nveh_fixe):>14.1f}")
        if costs_adaptatif:
            print(f"  {'Flotte mélange ADAPTATIF (v2)':<30} {statistics.mean(costs_adaptatif):>18.2f} {statistics.mean(nveh_adaptatif):>14.1f}")

        if costs_fixe and costs_adaptatif:
            gain_adapt_vs_fixe = (statistics.mean(costs_fixe) - statistics.mean(costs_adaptatif)) / statistics.mean(costs_fixe) * 100
            print(f"\n  -> Gain ADAPTATIF (v2) vs FIXE : {gain_adapt_vs_fixe:+.1f}%")

    print("\n" + "=" * 70)
    print("INTERPRETATION :")
    print("  - Si l'adaptatif bat le fixe surtout aux extremes (tres dense")
    print("    ou tres disperse), l'heuristique de dispersion capture un")
    print("    signal reel -> base solide pour un futur modele ML.")
    print("  - Si le gain est nul/negligeable partout, l'heuristique simple")
    print("    n'apporte rien de plus que le melange fixe -> chercher un")
    print("    autre signal, ou accepter le melange fixe comme suffisant.")
    print("=" * 70)


if __name__ == '__main__':
    main()