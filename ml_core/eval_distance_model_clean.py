"""
eval_distance_model_clean.py
==============================
Le MAE de 1.224 km obtenu precedemment (compare_distance_fallback.py)
est evalue sur train+test confondus -> biais optimiste, le modele a
"vu" une partie de ces points pendant l'entrainement.

Ce script refait le MEME split train/test que train_distance.py
(test_size=0.2, random_state=42 -> IDENTIQUE, donc le jeu de test ici
est exactement celui que le modele n'a JAMAIS vu) et calcule le MAE
uniquement sur ce jeu de test propre. C'est CE chiffre qu'il faut citer
dans le memoire, pas celui du script de comparaison rapide.

Usage (depuis le dossier ml_core):
    python eval_distance_model_clean.py
"""
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'dataset_distances_tunis.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'model_distance.pkl')


def main():
    df = pd.read_csv(CSV_PATH).dropna()

    X = df[['lat1', 'lng1', 'lat2', 'lng2', 'distance_haversine']]
    y = df['distance_reelle_osrm']

    # MEME split que train_distance.py - donc X_test ici == X_test
    # original, jamais vu par le modele pendant fit().
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = joblib.load(MODEL_PATH)
    y_pred = model.predict(X_test)

    mae_model_clean = mean_absolute_error(y_test, y_pred)
    r2_model_clean = r2_score(y_test, y_pred)

    # Baselines evaluees sur CE MEME jeu de test (comparaison loyale)
    haversine_test = X_test['distance_haversine'].values
    pred_fixed_13 = haversine_test * 1.3
    mae_fixed = mean_absolute_error(y_test, pred_fixed_13)

    # Coefficient calibre sur le TRAIN uniquement (pas de fuite de donnees)
    haversine_train = X_train['distance_haversine'].values
    optimal_coef = np.sum(haversine_train * y_train.values) / np.sum(haversine_train ** 2)
    pred_optimal_coef = haversine_test * optimal_coef
    mae_optimal_coef = mean_absolute_error(y_test, pred_optimal_coef)

    print("="*70)
    print("EVALUATION PROPRE (jeu de test jamais vu par le modele)")
    print("="*70)
    print(f"Taille jeu de test : {len(X_test)} paires (sur {len(df)} total)\n")
    print(f"{'Méthode':<45} {'MAE (km)':>12}")
    print("-"*70)
    print(f"{'Multiplicateur fixe (x1.3)':<45} {mae_fixed:>12.3f}")
    print(f"{'Multiplicateur calibré (x' + f'{optimal_coef:.3f}, sur train)':<45} {mae_optimal_coef:>12.3f}")
    print(f"{'Random Forest (model_distance.pkl)':<45} {mae_model_clean:>12.3f}")
    print(f"{'  R² du Random Forest sur ce jeu de test':<45} {r2_model_clean:>12.3f}")
    print("="*70)

    gain = (mae_fixed - mae_model_clean) / mae_fixed * 100
    print(f"\nGain RF vs multiplicateur fixe (évaluation NON biaisée) : {gain:+.1f}%")
    print("\n-> C'est CE chiffre (MAE et gain%) qu'il faut citer dans le mémoire,")
    print("   pas celui de compare_distance_fallback.py qui était biaisé en")
    print("   faveur du modèle (évaluation sur train+test mélangés).")


if __name__ == '__main__':
    main()