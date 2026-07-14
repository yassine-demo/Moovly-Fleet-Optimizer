#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_flotte_adaptative.py

Compare les performances entre :
- Capacité fixe (ex: 4, 3, 2 places)
- Capacité mixte générée par heuristique adaptative (construire_flotte_adaptative)
- Optionnel : prédiction ML si disponible (predire_flotte_ia)

Utilisation :
    python benchmark_flotte_adaptative.py --file testi.xlsx --destination "33 Rue des Entrepreneurs, Tunis 2035"

Résultats :
    - Affichage dans la console (tableau comparatif)
    - Export CSV : benchmark_resultats.csv
"""

import os
import sys
import argparse
import time
import csv
from datetime import datetime

# Ajouter le chemin du projet pour importer moovly_system
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moovly_system import (
    charger_employes_excel,
    geocoder_lieu,
    solve_vrp_ortools,
    build_suggestion_from_routes,
    construire_flotte_adaptative,
    predire_flotte_ia,
    distance_haversine_km,
    PARAMS_RSE
)


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================
def charger_employes_avec_geocodage(filepath):
    """
    Charge les employés depuis un Excel. Si les colonnes Latitude/Longitude
    sont absentes, géocode automatiquement les adresses via Nominatim.
    """
    import pandas as pd
    import numpy as np

    df = pd.read_excel(filepath)

    # Détection automatique des colonnes
    dest_col = None
    for col in df.columns:
        if str(col).lower().strip() in ['destination', 'destinations', 'adresse', 'lieu']:
            dest_col = col
            break

    if dest_col is None:
        raise ValueError("Aucune colonne 'Destination' trouvée dans le fichier.")

    # Détection des colonnes de coordonnées
    lat_col = None
    lng_col = None
    nom_col = None

    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ['latitude', 'lat']:
            lat_col = col
        elif col_lower in ['longitude', 'lng', 'lon']:
            lng_col = col
        elif col_lower in ['nom', 'name']:
            nom_col = col

    employes = []
    for idx, row in df.iterrows():
        nom = str(row.get(nom_col, f"Employé {idx+1}")).strip() if nom_col else f"Employé {idx+1}"
        adresse = str(row.get(dest_col, '')).strip()
        if not adresse or adresse == 'nan':
            continue

        # Vérifier si des coordonnées sont déjà présentes
        lat = None
        lng = None
        if lat_col and lng_col:
            try:
                lat_val = row.get(lat_col)
                lng_val = row.get(lng_col)
                if pd.notna(lat_val) and pd.notna(lng_val):
                    lat = float(lat_val)
                    lng = float(lng_val)
            except (ValueError, TypeError):
                pass

        # Si pas de coordonnées, on géocode
        if lat is None or lng is None:
            coords = geocoder_lieu(adresse)
            if coords:
                lat, lng = coords
                print(f"   ✅ Géocodé : {adresse} → ({lat:.6f}, {lng:.6f})")
            else:
                print(f"   ⚠️ Échec géocodage pour : {adresse}")
                continue

        employes.append({
            'id': f'E{idx+1}',
            'nom': nom,
            'residence': adresse,
            'lat': lat,
            'lng': lng,
            '_id': f'emp_{idx}'
        })

    return employes


def charger_destination_manuellement(nom_lieu):
    """
    Charge une destination manuellement via géocodage.
    """
    coords = geocoder_lieu(nom_lieu)
    if coords:
        return {'nom': nom_lieu, 'lat': coords[0], 'lng': coords[1], '_id': 'dest_manual'}
    raise ValueError(f"Impossible de géocoder la destination : {nom_lieu}")


def extraire_metriques(suggestion):
    """
    Extrait les métriques principales d'une suggestion (objet retourné par build_suggestion_from_routes).
    """
    return {
        'distance_km': suggestion['distance_km'],
        'duree_min': suggestion['duree_min'],
        'nb_vehicules': len(suggestion['routes']),
        'nb_employes': sum(len(r['ordre']) for r in suggestion['routes']),
        'cout_total': suggestion['tarif']['final'],
        'co2_kg': suggestion['rse_metrics']['co2_scenario_moovly'],
        'co2_evite_kg': suggestion['rse_metrics']['co2_saved_kg'],
        'cout_evite_tnd': suggestion['rse_metrics']['cost_saved_tnd'],
        'taux_remplissage': suggestion['rse_metrics']['fill_rate_percent'],
        'score_composite': suggestion.get('score_composite', 0)
    }


def executer_scenario(employes, destination, capacites_flotte, label, temps_limite=300):
    """
    Exécute l'optimisation VRP avec la flotte donnée et retourne les métriques.
    """
    print(f"\n🚀 Exécution du scénario : {label}")
    print(f"   Flotte : {capacites_flotte}")

    start_time = time.time()
    routes = solve_vrp_ortools(employes, destination, capacites_flotte, time_limit_sec=temps_limite)
    elapsed = time.time() - start_time

    if routes is None:
        print("   ⚠️ Aucune solution trouvée.")
        return None

    # Construire la suggestion avec les métriques RSE
    suggestion = build_suggestion_from_routes(routes, destination, employes, capacites_flotte, label)
    metriques = extraire_metriques(suggestion)
    metriques['temps_calcul_s'] = round(elapsed, 2)
    metriques['flotte'] = str(capacites_flotte)
    metriques['label'] = label

    print(f"   ✅ {metriques['nb_vehicules']} véhicules, {metriques['distance_km']} km, {metriques['cout_total']} TND, {metriques['co2_kg']} kg CO₂")
    return metriques


# =============================================================================
# SCÉNARIOS DE COMPARAISON
# =============================================================================
def generer_scenarios(employes, destination, utiliser_ml=False):
    """
    Génère la liste des scénarios à comparer.
    Retourne une liste de tuples (label, capacites_flotte)
    """
    scenarios = []

    # Capacités fixes courantes
    for cap in [4, 3, 2]:
        scenarios.append((f"Capacité fixe {cap} places", [cap] * len(employes)))

    # Flotte adaptative (heuristique)
    flotte_adapt = construire_flotte_adaptative(employes)
    scenarios.append((f"Flotte adaptative (heuristique) : {flotte_adapt}", flotte_adapt))

    # Flotte prédite par ML (si disponible)
    if utiliser_ml:
        try:
            flotte_ml = predire_flotte_ia(employes, destination)
            if flotte_ml and len(flotte_ml) > 0:
                scenarios.append((f"Flotte ML : {flotte_ml}", flotte_ml))
            else:
                print("[INFO] Prédiction ML vide ou non disponible.")
        except Exception as e:
            print(f"[INFO] Erreur lors de la prédiction ML : {e}")

    return scenarios


# =============================================================================
# AFFICHAGE ET EXPORT
# =============================================================================
def afficher_resultats(resultats):
    """
    Affiche un tableau comparatif des résultats dans la console.
    """
    print("\n" + "=" * 120)
    print("📊 RÉSULTATS DE LA COMPARAISON")
    print("=" * 120)

    headers = ['Scénario', 'Véhicules', 'Employés', 'Distance (km)', 'Durée (min)',
               'Coût (TND)', 'CO₂ (kg)', 'Taux rempl. (%)', 'CO₂ évité (kg)',
               'Économie (TND)', 'Temps calc. (s)']
    col_widths = [28, 10, 10, 14, 13, 14, 12, 16, 15, 14, 14]

    header_line = ""
    for h, w in zip(headers, col_widths):
        header_line += f"{h:>{w}}"
    print(header_line)
    print("-" * 120)

    for r in resultats:
        ligne = (
            f"{r['label'][:27]:>{col_widths[0]}}",
            f"{r['nb_vehicules']:>{col_widths[1]}}",
            f"{r['nb_employes']:>{col_widths[2]}}",
            f"{r['distance_km']:>{col_widths[3]}.2f}",
            f"{r['duree_min']:>{col_widths[4]}.1f}",
            f"{r['cout_total']:>{col_widths[5]}.2f}",
            f"{r['co2_kg']:>{col_widths[6]}.2f}",
            f"{r['taux_remplissage']:>{col_widths[7]}.1f}",
            f"{r['co2_evite_kg']:>{col_widths[8]}.2f}",
            f"{r['cout_evite_tnd']:>{col_widths[9]}.2f}",
            f"{r['temps_calcul_s']:>{col_widths[10]}.2f}"
        )
        print(" ".join(ligne))

    print("=" * 120)


def exporter_csv(resultats, nom_fichier="benchmark_resultats.csv"):
    if not resultats:
        return
    keys = resultats[0].keys()
    with open(nom_fichier, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys, delimiter=';')
        writer.writeheader()
        writer.writerows(resultats)
    print(f"\n✅ Résultats exportés dans {nom_fichier}")


# =============================================================================
# SCRIPT PRINCIPAL
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Benchmark capacité fixe vs mixte pour Moovly Fleet Optimizer")
    parser.add_argument('--file', type=str, required=True, help="Fichier Excel contenant les employés")
    parser.add_argument('--destination', type=str, default="33 Rue des Entrepreneurs, Tunis 2035",
                        help="Nom ou adresse de la destination (sera géocodée)")
    parser.add_argument('--time', type=int, default=300, help="Temps limite pour OR-Tools (secondes)")
    parser.add_argument('--ml', action='store_true', help="Utiliser la prédiction ML si disponible")
    parser.add_argument('--csv', type=str, default="benchmark_resultats.csv", help="Nom du fichier CSV de sortie")
    args = parser.parse_args()

    print("\n🔍 CHARGEMENT DES DONNÉES")
    print("-" * 40)

    if not os.path.exists(args.file):
        print(f"❌ Fichier introuvable : {args.file}")
        sys.exit(1)

    # Charger les employés avec géocodage automatique
    employes = charger_employes_avec_geocodage(args.file)
    if not employes:
        print("❌ Aucun employé chargé ou géocodé.")
        sys.exit(1)

    print(f"✅ {len(employes)} employés chargés et géolocalisés.")

    # Charger destination
    destination = charger_destination_manuellement(args.destination)
    print(f"✅ Destination : {destination['nom']} ({destination['lat']:.6f}, {destination['lng']:.6f})")

    # Générer les scénarios
    scenarios = generer_scenarios(employes, destination, utiliser_ml=args.ml)

    # Exécuter chaque scénario
    resultats = []
    for label, flotte in scenarios:
        if len(flotte) == 0:
            print(f"⚠️ Scénario {label} ignoré : flotte vide.")
            continue
        metriques = executer_scenario(employes, destination, flotte, label, temps_limite=args.time)
        if metriques:
            resultats.append(metriques)

    if not resultats:
        print("❌ Aucun résultat obtenu.")
        sys.exit(1)

    afficher_resultats(resultats)
    exporter_csv(resultats, args.csv)

    # Meilleur scénario (par distance)
    best = min(resultats, key=lambda x: x['distance_km'])
    print(f"\n🏆 MEILLEUR SCÉNARIO : {best['label']}")
    print(f"   Distance : {best['distance_km']} km, {best['nb_vehicules']} véhicules, coût {best['cout_total']} TND, CO₂ {best['co2_kg']} kg")
    print("\n✅ Benchmark terminé.")


if __name__ == "__main__":
    main()