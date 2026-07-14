import pandas as pd
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

print(" Chargement des données de distances...")
dossier_actuel = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(dossier_actuel, 'dataset_distances_tunis.csv'))

# Nettoyage de sécurité (au cas où OSRM aurait échoué sur quelques lignes)
df = df.dropna()

# 1. Définir les Features (X) et la Target (y)
X = df[['lat1', 'lng1', 'lat2', 'lng2', 'distance_haversine']]
y = df['distance_reelle_osrm']

# 2. Séparer en données d'entraînement (80%) et de test (20%)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. Choix de l'algorithme : Random Forest (très performant pour les relations non-linéaires géospatiales)
print(" Entraînement du modèle de régression (Random Forest)...")
modele_distance = RandomForestRegressor(n_estimators=100, random_state=42)
modele_distance.fit(X_train, y_train)

# 4. Évaluation scientifique
y_pred = modele_distance.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("\n --- RÉSULTATS DU MODÈLE DE DISTANCE ---")
print(f" MAE (Erreur Absolue Moyenne) : {mae:.3f} km")
print(f" R² (Score de précision globale) : {r2:.3f} (1.0 = parfait)")
print("Le modèle se trompe en moyenne de seulement", round(mae*1000), "mètres par rapport à la réalité d'OSRM.")

# 5. Sauvegarde du modèle pour l'utiliser dans Flask
chemin_modele = os.path.join(dossier_actuel, 'model_distance.pkl')
joblib.dump(modele_distance, chemin_modele)
print(f"\nModèle sauvegardé sous : {chemin_modele}")