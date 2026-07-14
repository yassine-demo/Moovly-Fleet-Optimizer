"""
benchmark_warmstart.py
=======================
Mesure HONNETE de l'apport du warm-start ML.

Ce que le warm-start peut legitimement ameliorer :
  - Temps de convergence (vitesse) vers une bonne solution
  - Qualite de la solution a TEMPS LIMITE EGAL (anytime quality)

Ce que le warm-start NE PEUT PAS ameliorer :
  - La solution optimale finale si on laisse le solveur tourner
    suffisamment longtemps (OR-Tools convergera vers le meme
    voisinage de qualite avec ou sans warm-start, donne assez de temps)

=> Le bon test : comparer a TEMPS LIMITE COURT ET IDENTIQUE (le cas reel
   en production, ou ortools_time_limit_s est petit pour rester reactif).

Usage:
    python benchmark_warmstart.py
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
    """Cout approx en distance (Haversine) pour comparer objectivement
    sans dependre d'appels OSRM (qui ajouteraient du bruit reseau au benchmark)."""
    total = 0.0
    for route in routes:
        pts = route + [destination]
        for i in range(len(pts) - 1):
            total += ms.distance_haversine_km(
                pts[i]['lat'], pts[i]['lng'], pts[i+1]['lat'], pts[i+1]['lng']
            )
    return total


def run_single_trial(n_employes, capacite, time_limit_s, seed, use_warmstart):
    employes = generer_employes(n_employes, seed=seed)

    # Active/desactive le modele de warm-start pour ce trial
    original_model = ms.MODEL_WARMSTART
    if not use_warmstart:
        ms.MODEL_WARMSTART = None

    t0 = time.perf_counter()
    routes = ms.solve_vrp_ortools(employes, DESTINATION, capacite, time_limit_sec=time_limit_s)
    elapsed = time.perf_counter() - t0

    ms.MODEL_WARMSTART = original_model

    if not routes:
        return None

    cost = route_total_distance_haversine(routes, DESTINATION)
    n_vehicles = len(routes)
    return {'time_s': elapsed, 'cost_km': cost, 'n_vehicles': n_vehicles}


def main():
    if ms.MODEL_WARMSTART is None:
        print("ERREUR: model_warmstart.pkl n'est pas charge. "
              "Verifiez le chemin ml_core/model_warmstart.pkl")
        return

    print("="*70)
    print("BENCHMARK : OR-Tools AVEC vs SANS warm-start ML")
    print("="*70)

    # Scenarios realistes : tailles variees, temps limite COURT et EGAL
    # (le cas qui compte en production, pas un temps limite genereux)
    configs = [
        {'n_employes': 15, 'capacite': 3, 'time_limit_s': 60},
        {'n_employes': 25, 'capacite': 3, 'time_limit_s': 60},
        {'n_employes': 35, 'capacite': 4, 'time_limit_s': 60},
        {'n_employes': 50, 'capacite': 4, 'time_limit_s': 60},
    ]
    n_seeds = 8  # repeter chaque config avec plusieurs tirages aleatoires

    for cfg in configs:
        print(f"\n--- n={cfg['n_employes']} employes, capacite={cfg['capacite']}, "
              f"time_limit={cfg['time_limit_s']}s, {n_seeds} essais ---")

        costs_with, costs_without = [], []
        times_with, times_without = [], []

        for seed in range(n_seeds):
            r_with = run_single_trial(cfg['n_employes'], cfg['capacite'],
                                       cfg['time_limit_s'], seed, use_warmstart=True)
            r_without = run_single_trial(cfg['n_employes'], cfg['capacite'],
                                          cfg['time_limit_s'], seed, use_warmstart=False)
            if r_with and r_without:
                costs_with.append(r_with['cost_km'])
                costs_without.append(r_without['cost_km'])
                times_with.append(r_with['time_s'])
                times_without.append(r_without['time_s'])

        if not costs_with:
            print("  Aucun essai valide.")
            continue

        avg_cost_with = statistics.mean(costs_with)
        avg_cost_without = statistics.mean(costs_without)
        avg_time_with = statistics.mean(times_with)
        avg_time_without = statistics.mean(times_without)

        gain_cost_pct = (avg_cost_without - avg_cost_with) / avg_cost_without * 100
        gain_time_pct = (avg_time_without - avg_time_with) / avg_time_without * 100

        print(f"  Cout moyen   AVEC warm-start: {avg_cost_with:.2f} km")
        print(f"  Cout moyen   SANS warm-start: {avg_cost_without:.2f} km")
        print(f"  -> Gain qualite: {gain_cost_pct:+.1f}%")
        print(f"  Temps moyen  AVEC warm-start: {avg_time_with:.2f} s")
        print(f"  Temps moyen  SANS warm-start: {avg_time_without:.2f} s")
        print(f"  -> Gain vitesse: {gain_time_pct:+.1f}%")

    print("\n" + "="*70)
    print("INTERPRETATION:")
    print("  - Si gain qualite > 0 a temps limite COURT: le warm-start aide")
    print("    a trouver une meilleure solution avant l'echeance.")
    print("  - Si gain quasi nul: le warm-start n'apporte rien de mesurable")
    print("    sur cette taille de probleme / ce time_limit -> a documenter")
    print("    honnetement dans le memoire (limite identifiee, pas cachee).")
    print("="*70)


if __name__ == '__main__':
    main()