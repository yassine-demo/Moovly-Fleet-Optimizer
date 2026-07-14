import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

def entrainer_modele_flotte():
    path_dataset = os.path.join("ml_core", "dataset_fleet_optimization.csv")
    if not os.path.exists(path_dataset):
        print(" Erreur : Le dataset n'existe pas. Lancez d'abord le script de génération.")
        return

    df = pd.read_csv(path_dataset)

    # Définition des features (X) et de la cible (y)
    X = df[['n_employes', 'dist_moyenne', 'dist_std', 'dist_max', 'dispersion_lat', 'dispersion_lng', 'bbox_area']]
    y = df['label_strategie_flotte']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Entraînement du modèle RandomForest pour la configuration de la flotte...")
    model = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42)
    model.fit(X_train, y_train)

    # Évaluation
    predictions = model.predict(X_test)
    acc = accuracy_score(y_test, predictions)
    print(f"Précision du modèle (Accuracy) : {acc * 100:.2f}%")
    print("\nRapport de Classification détaillé :")
    print(classification_report(y_test, predictions))

    # Sauvegarde du fichier .pkl
    model_path = os.path.join("ml_core", "model_fleet_strategy.pkl")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print("Modèle 'model_fleet_strategy.pkl' sauvegardé avec succès dans 'ml_core/' !")

if __name__ == "__main__":
    import os
    entrainer_modele_flotte()