import pandas as pd
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, classification_report
import joblib

print(" Chargement des données Warm-Start...")
dossier_actuel = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(dossier_actuel, 'dataset_warmstart_pairs.csv'))
df = df.dropna()

# 1. Définir les Features (X) et la Target (y)
X = df[['dist_entre_employes', 'dist_A_destination', 'dist_B_destination', 'taille_groupe_total']]
y = df['sont_ensemble']

# 2. Train / Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. Entraînement du Classifieur
print(" Entraînement du modèle de classification...")
modele_warmstart = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
modele_warmstart.fit(X_train, y_train)

# 4. Évaluation scientifique
y_pred = modele_warmstart.predict(X_test)
precision = precision_score(y_test, y_pred)
accuracy = accuracy_score(y_test, y_pred)

print("\n --- RÉSULTATS DU MODÈLE WARM-START ---")
print(f" Précision (sur les 'Oui') : {precision:.2%}")
print(f" Exactitude globale (Accuracy) : {accuracy:.2%}")
print("\n Rapport détaillé (Classification Report) :")
print(classification_report(y_test, y_pred))

# 5. Sauvegarde du modèle
chemin_modele = os.path.join(dossier_actuel, 'model_warmstart.pkl')
joblib.dump(modele_warmstart, chemin_modele)
print(f"\n Modèle sauvegardé sous : {chemin_modele}")