#!/usr/bin/env python3

import os
import sys
import subprocess
import json

# Ajouter le chemin du projet
sys.path.insert(0, '/mnt/nas/test/git_manager_app')

# Fonction pour vérifier les remotes

def check_remotes():
    # Exécuter la commande Django pour vérifier les remotes
    result = subprocess.run(
        ["python", "manage.py", "check_remotes", "--verbose"],
        capture_output=True,
        text=True,
        cwd='/mnt/nas/test/git_manager_app'
    )
    
    # Afficher le résultat
    print(result.stdout)
    
    # Extraire les alertes
    if result.returncode == 0:
        # Vérifier si des alertes ont été trouvées
        if "alerts" in result.stdout:
            print("⚠️ Alertes détectées :")
            # Extraire les alertes
            alerts = json.loads(result.stdout)
            if alerts.get('count') > 0:
                print(f"Nombre d'alertes : {alerts['count']}")
                for alert in alerts['alerts']:
                    print(f"  - {alert['repo']}/{alert['remote']} ({alert['branch']}): {alert['status']} ({alert['ahead']} ahead, {alert['behind']} behind)")
    
    return result.returncode == 0

if __name__ == "__main__":
    check_remotes()