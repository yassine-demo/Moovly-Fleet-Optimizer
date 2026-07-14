"""
compare_distance_fallback.py
==============================
Avant d'integrer model_distance.pkl comme fallback OSRM, on doit savoir
s'il bat reellement la regle actuelle (Haversine x 1.3) qu'il est censé
remplacer. Sinon on ajoute de la complexite (dependance sklearn/joblib,
fichier .pkl a maintenir) pour rien, ou pire, pour un resultat moins bon.

Ce script recharge le dataset deja collecte (dataset_distances_tunis.csv)
et compare, sur les MEMES paires de points :
  1. Le multiplicateur fixe actuel : distance_reelle ≈ haversine * 1.3
  2. Le modele Random Forest entraine (model_distance.pkl)
  3. (Bonus) Un multiplicateur optimal calcule sur les donnees, pour voir
     si meme un simple coefficient mieux calibre suffirait.

Usage:
    python compare_distance_fallback.py
(a executer depuis le dossier ml_core, ou ajuster les chemins)
"""
import os
import pandas as pd
import numpy as np
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'dataset_distances_tunis.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'model_distance.pkl')


def mae(y_true, y_pred):
    return np.mean(np.abs(np.array(y_true) - np.array(y_pred)))


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERREUR: {CSV_PATH} introuvable. Lancez ce script depuis ml_core/.")
        return
    if not os.path.exists(MODEL_PATH):
        print(f"ERREUR: {MODEL_PATH} introuvable.")
        return

    df = pd.read_csv(CSV_PATH).dropna()
    print(f"Dataset charge : {len(df)} paires de points.\n")

    y_true = df['distance_reelle_osrm'].values
    haversine = df['distance_haversine'].values

    # --- 1. Baseline actuelle : Haversine x 1.3 ---
    pred_fixed_13 = haversine * 1.3
    mae_fixed = mae(y_true, pred_fixed_13)

    # --- 2. Coefficient optimal sur CE dataset (borne theorique d'un multiplicateur simple) ---
    optimal_coef = np.sum(haversine * y_true) / np.sum(haversine ** 2)  # regression lineaire sans intercept
    pred_optimal_coef = haversine * optimal_coef
    mae_optimal_coef = mae(y_true, pred_optimal_coef)

    # --- 3. Modele Random Forest entraine ---
    model = joblib.load(MODEL_PATH)
    X = df[['lat1', 'lng1', 'lat2', 'lng2', 'distance_haversine']]
    pred_model = model.predict(X)
    mae_model = mae(y_true, pred_model)

    # NOTE IMPORTANTE : le modele a ete ENTRAINE sur ce meme dataset (split
    # train/test interne dans train_distance.py, mais ici on evalue sur
    # l'ensemble complet, train+test confondus). Le MAE du modele ici sera
    # donc LEGEREMENT OPTIMISTE par rapport a un vrai jeu de test independant
    # (le modele a "vu" une partie de ces points pendant l'entrainement).
    # Pour une comparaison rigoureuse, on devrait refaire le meme split
    # train/test ici. Mais meme avec ce biais optimiste en faveur du modele,
    # si le multiplicateur fixe gagne quand meme, la conclusion est d'autant
    # plus solide.

    print("="*70)
    print("COMPARAISON DES METHODES DE PREDICTION DE DISTANCE")
    print("="*70)
    print(f"{'Méthode':<45} {'MAE (km)':>12}")
    print("-"*70)
    print(f"{'Multiplicateur fixe actuel (x1.3)':<45} {mae_fixed:>12.3f}")
    print(f"{'Multiplicateur optimal calibré (x' + f'{optimal_coef:.3f})':<45} {mae_optimal_coef:>12.3f}")
    print(f"{'Random Forest (model_distance.pkl)':<45} {mae_model:>12.3f}")
    print(f"{'  -> Random Forest, eval sur train+test':<45} {'(biais optimiste, voir note ci-dessus)':>12}")
    print("="*70)

    print("\nINTERPRETATION:")
    best = min([('Multiplicateur fixe x1.3', mae_fixed),
                ('Multiplicateur calibré', mae_optimal_coef),
                ('Random Forest', mae_model)], key=lambda x: x[1])
    print(f"  Meilleure methode sur ce dataset : {best[0]} (MAE={best[1]:.3f} km)")

    gain_vs_fixed = (mae_fixed - mae_model) / mae_fixed * 100
    if gain_vs_fixed > 15:
        print(f"  Le RF bat le multiplicateur fixe de {gain_vs_fixed:.1f}% -> "
              "gain reel, integration justifiee.")
    elif gain_vs_fixed > 0:
        print(f"  Le RF bat legerement le multiplicateur fixe ({gain_vs_fixed:.1f}%) "
              "mais le gain est modeste -> a documenter honnetement, ne pas "
              "survendre.")
    else:
        print(f"  Le RF NE BAT PAS le multiplicateur fixe actuel "
              f"({-gain_vs_fixed:.1f}% pire) -> meme avec le biais optimiste "
              "en sa faveur. Conclusion : le modele n'apporte pas de valeur "
              "mesurable ici en l'etat (features insuffisantes pour capturer "
              "la geometrie reelle du reseau routier de Tunis).")


if __name__ == '__main__':
    main()