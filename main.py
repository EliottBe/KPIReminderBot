import requests
import json
from time import sleep
from datetime import datetime
import os
# Configuration initiale
api_key = os.environ.get('MONDAY_SECRET')
slack_token = os.environ.get('SLACK_SECRET')
headers = {"Authorization": api_key}
board_id = "5215958843"


# Fonction pour récupérer les données KPI de Monday.com


def fetch_kpi_data():
    print("Étape 1: Récupération des données KPI de Monday.com")
    query = f"""
    {{
      boards(ids: {board_id}) {{
        groups {{
          items (limit: 10){{
            name
            id
            column_values {{
              id
              title
              value
            }}
          }}
        }}
      }}
    }}"""
    response = requests.post('https://api.monday.com/v2',
                             json={'query': query}, headers=headers)
    return response.json()


# Fonction pour récupérer l'e-mail d'un utilisateur à partir de son ID dans Monday.com


def fetch_user_email_from_monday(user_id):
    print(
        f"Étape 2: Récupération de l'e-mail de l'utilisateur {user_id} de Monday.com")
    query = f"""
    query {{
      users(ids: [{user_id}]) {{
        id
        email
      }}
    }}"""
    response = requests.post('https://api.monday.com/v2',
                             json={'query': query}, headers=headers)
    data = response.json()
    users = data.get('data', {}).get('users', [])
    if users:
        return users[0].get('email')
    return None


# Fonction pour obtenir l'ID Slack à partir de l'e-mail


def get_slack_user_id_from_email(slack_token, email):
    print(f"Étape 3: Récupération de l'ID Slack de l'utilisateur {email}")
    url = 'https://slack.com/api/users.lookupByEmail'
    headers = {'Authorization': f'Bearer {slack_token}'}
    params = {'email': email}
    response = requests.get(url, headers=headers, params=params)
    user_data = response.json()
    if user_data.get('ok'):
        return user_data['user']['id']
    else:
        print(
            f"Impossible de trouver l'utilisateur Slack avec l'e-mail {email}. Erreur: {user_data.get('error')}")
        return None


# Fonction pour envoyer un message détaillé à l'utilisateur Slack


def send_kpi_message_to_user(slack_token, user_id, kpi_name):
    print(f"Étape 4: Envoi du message Slack à l'utilisateur {user_id}")
    message_text = f"*Rappel pour mettre à jour le KPI* : *{kpi_name}*."

    url = 'https://slack.com/api/chat.postMessage'
    headers = {'Authorization': f'Bearer {slack_token}'}
    payload = {
        'channel': user_id,
        'text': message_text,
        'mrkdwn': True
    }
    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()
    if response_data.get('ok'):
        return response_data  # ID du message
    return None


def read_thread_replies(slack_token, channel_id, thread_ts):
    url = 'https://slack.com/api/conversations.replies'
    headers = {'Authorization': f'Bearer {slack_token}'}
    params = {
        'channel': channel_id,
        'ts': thread_ts
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()


def fetch_subitem_column_ids(item_id):
    query = f"""
    {{
      items(ids: {item_id}) {{
        subitems {{
          board {{
            columns {{
              id
              title
            }}
          }}
        }}
      }}
    }}"""
    response = requests.post('https://api.monday.com/v2',
                             json={'query': query}, headers=headers)
    return response.json()


def update_monday_column(board_id, item_id, column_id, value):
    print(f"Étape 5: Mise à jour de la dernière valeur dans Monday : {value}")
    query = """
    mutation ($myBoardId: Int!, $myItemId: Int!, $myColumnId: String!, $myValue: JSON!) {
      change_column_value (
        board_id: $myBoardId, 
        item_id: $myItemId, 
        column_id: $myColumnId, 
        value: $myValue
      ) {
        id
      }
    }
    """
    variables = {
        'myBoardId': int(board_id),
        'myItemId': int(item_id),
        'myColumnId': column_id,
        'myValue': json.dumps(str(value))
    }
    response = requests.post('https://api.monday.com/v2', json={'query': query, 'variables': variables},
                             headers=headers)
    return response.json()


def create_subitem_in_monday(item_id, value_to_add):
    print(f"Étape 6 : Création du sous-élément permettant de suivre l'historique des valeurs dans Monday.")

    # Étape 1: Créer le sous-élément
    current_date = datetime.now().strftime("%Y-%m-%d")
    query = """
    mutation ($myParentItemId: Int!, $myItemName: String!) {
      create_subitem (
        parent_item_id: $myParentItemId, 
        item_name: $myItemName
      ) {
        id
      }
    }
    """
    # Utilisation de la date courante pour le nom du sous-élément
    variables = {
        'myParentItemId': int(item_id),
        'myItemName': f"Valeur du {current_date}"
    }
    response = requests.post('https://api.monday.com/v2', json={'query': query, 'variables': variables},
                             headers=headers)
    subitem_data = response.json()
    subitem_id = subitem_data.get("data", {}).get("create_subitem", {}).get("id")

    if not subitem_id:
        print("Échec de la création du sous-élément.")
        return

    # Ici, nous utilisons l'ID de l'élément parent pour mettre à jour le sous-élément
    # Ajustez les identifiants de colonne en fonction de votre tableau
    random_value_column_id = "name"
    date_column_id = "date0"
    value_column_id = "chiffres"

    # Format JSON pour la date
    date_json = json.dumps({"date": current_date})

    # Mettre à jour la colonne "Valeur aléatoire"
    update_response = update_monday_column(item_id, subitem_id, random_value_column_id, "Valeur aléatoire")
    print(update_response)

    # Mettre à jour la colonne "Date"
    update_response = update_monday_column(item_id, subitem_id, date_column_id, date_json)
    print(update_response)

    # Mettre à jour la colonne "Valeur"
    update_response = update_monday_column(item_id, subitem_id, value_column_id, str(value_to_add))
    print(update_response)

def send_kpi_reminders_to_users():
    print("Démarrage du processus de rappel KPI.")

    monday_data = fetch_kpi_data()

    for board in monday_data.get('data', []).get('boards', []):
        for group in board.get('groups', []):
            for item in group.get('items', []):
                kpi_name = item.get('name', '')
                kpi_id = item.get('id', '')

                responsible_id = None

                for column in item.get('column_values', []):
                    if column['id'] == 'personnes':
                        persons_and_teams = json.loads(column['value'] or '{}')
                        responsible_id = persons_and_teams.get(
                            'personsAndTeams', [{}])[0].get('id')

                if responsible_id:
                    email = fetch_user_email_from_monday(responsible_id)

                    if email:
                        slack_user_id = get_slack_user_id_from_email(
                            slack_token, email)

                        if slack_user_id:
                            slack_response = send_kpi_message_to_user(
                                slack_token, slack_user_id, kpi_name)
                            channel_id = slack_response.get('channel')
                            thread_ts = slack_response.get('ts')

                            replies = []

                            while len(replies) < 2:
                                replies = read_thread_replies(slack_token, channel_id, thread_ts).get('messages')
                                sleep(1)

                            value_to_add = float(replies[1].get('text'))

                            # Mettre à jour la colonne "chiffres3" de l'élément principal
                            update_monday_column(board_id, kpi_id, "chiffres3", value_to_add)

                            # Créer un nouveau sous-élément
                            create_subitem_in_monday(kpi_id, value_to_add)

                            print(f"Tout s'est bien passé, fin des actions pour le KPI {kpi_name}")


# Exécuter la fonction principale
send_kpi_reminders_to_users()
