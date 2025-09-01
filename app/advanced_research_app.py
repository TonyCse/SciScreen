import io
import re
from datetime import datetime, timedelta

import mysql.connector
import pandas as pd
import plotly.express as px
import streamlit as st
from werkzeug.security import check_password_hash


# === CONNEXION MYSQL ===
def get_connection():
    return mysql.connector.connect(
        host="srv494.hstgr.io",
        user="u499568465_tonycseresznya",
        password="Sci771025!",
        database="u499568465_Sci",
    )


# === USERS AUTH ===
def check_user(username, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user and check_password_hash(user["password"], password):
        return True
    return False


# === ARTICLES BDD ===
def insert_article_in_db(article_data, status, user):
    conn = get_connection()
    cursor = conn.cursor()

    # D'abord vérifier si les nouvelles colonnes existent, sinon les créer
    try:
        cursor.execute("DESCRIBE articles_tri")
        existing_columns = [col[0] for col in cursor.fetchall()]

        new_columns = [
            ("issn", "TEXT"),
            ("abs_lo_uo", "TEXT"),
            ("notes", "TEXT"),
            ("type_revue", "TEXT"),
            ("wl_mesure", "TEXT"),
            ("chir_participants", "TEXT"),
            ("specialiste", "TEXT"),
            ("intervention", "TEXT"),
            ("technique", "TEXT"),
            ("contexte", "TEXT"),
            ("simulation", "TEXT"),
            ("additional_outcomes", "TEXT"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE articles_tri ADD COLUMN {col_name} {col_type}",
                )

        conn.commit()
    except Exception as e:
        print(f"Erreur lors de l'ajout des colonnes: {e}")

    # Insérer l'article avec toutes les colonnes
    sql = """
    INSERT INTO articles_tri 
    (title, authors, journal, year, abstract, doi, url, issn, abs_lo_uo, notes, 
     type_revue, wl_mesure, chir_participants, specialiste, intervention, 
     technique, contexte, simulation, additional_outcomes, status, user, date_action)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
    """
    cursor.execute(
        sql,
        (
            article_data.get("title", ""),
            article_data.get("authors", ""),
            article_data.get("journal", ""),
            article_data.get("year", ""),
            article_data.get("abstract", ""),
            article_data.get("doi", ""),
            article_data.get("url", ""),
            article_data.get("issn", ""),
            article_data.get("abs_lo_uo", ""),
            article_data.get("notes", ""),
            article_data.get("type_revue", ""),
            article_data.get("wl_mesure", ""),
            article_data.get("chir_participants", ""),
            article_data.get("specialiste", ""),
            article_data.get("intervention", ""),
            article_data.get("technique", ""),
            article_data.get("contexte", ""),
            article_data.get("simulation", ""),
            article_data.get("additional_outcomes", ""),
            status,
            user,
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()


def fetch_articles_from_db(user=None):
    """Récupère les articles de la base, filtrés par utilisateur si fourni."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if user:
        cursor.execute(
            "SELECT * FROM articles_tri WHERE user = %s ORDER BY date_action DESC",
            (user,),
        )
    else:
        cursor.execute("SELECT * FROM articles_tri ORDER BY date_action DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(rows)


def delete_article_from_db(article_id):
    """Supprime un article de la base de données."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles_tri WHERE id = %s", (article_id,))
    conn.commit()
    cursor.close()
    conn.close()


def update_article_in_db(article_id, updated_data):
    """Met à jour un article dans la base de données avec les nouvelles données"""
    conn = get_connection()
    cursor = conn.cursor()

    # Convertir les types numpy en types Python natifs
    def convert_value(value):
        if pd.isna(value):
            return None
        if hasattr(value, "item"):  # numpy types
            return value.item()
        if isinstance(value, (int, float, str, bool)):
            return value
        return str(value)

    # Convertir toutes les valeurs
    converted_data = {key: convert_value(value) for key, value in updated_data.items()}
    converted_id = convert_value(article_id)

    # Construire la requête UPDATE dynamiquement
    set_clause = ", ".join([f"{key} = %s" for key in converted_data])
    sql = f"UPDATE articles_tri SET {set_clause} WHERE id = %s"

    # Valeurs à mettre à jour + l'ID
    values = list(converted_data.values()) + [converted_id]

    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()


# === UTILITAIRES ===
def smart_column_mapping(df):
    mappings = {
        "title": [
            "title",
            "article title",
            "titre",
            "nom",
            "article",
            "name",
            "article public author title",
        ],
        "authors": ["authors", "auteurs", "author"],
        "journal": ["journal name", "journal", "revue", "publication"],
        "year": ["publication year", "year", "année", "annee", "date"],
        "abstract": ["abstract", "abstract note", "résumé", "resume", "description"],
        "doi": ["doi"],
        "url": ["url", "link"],
        "issn": ["issn"],
        "abs_lo_uo": ["abs lo uo", "abs_lo_uo", "abslouo"],
        "notes": ["notes", "note"],
        "type_revue": ["type revue", "type_revue", "typerevue"],
        "wl_mesure": ["wl = mesure", "wl_mesure", "wlmesure"],
        "chir_participants": [
            "chir = participants",
            "chir_participants",
            "chirparticipants",
        ],
        "specialiste": ["specialiste", "spécialiste"],
        "intervention": ["intervention"],
        "technique": ["technique"],
        "contexte": ["contexte", "context"],
        "simulation": ["simulation"],
        "additional_outcomes": [
            "additional outcomes / exclusion",
            "additional_outcomes",
            "additionaloutcomes",
        ],
    }
    available_cols = df.columns.tolist()
    available_lower = [c.lower().strip() for c in available_cols]
    final_mapping = {}
    for target, options in mappings.items():
        for opt in options:
            if opt.lower() in available_lower:
                idx = available_lower.index(opt.lower())
                final_mapping[target] = available_cols[idx]
                break
    return final_mapping


def get_article_field(article, field_name, mapping, default=""):
    if field_name in mapping and mapping[field_name] in article:
        value = article[mapping[field_name]]
        if pd.notna(value):
            return str(value)
    return default


def safe_year_conversion(val, default="Année inconnue"):
    try:
        y = int(val)
        if 1800 < y < 2035:
            return str(y)
        return default
    except:
        return default


def highlight_text(text, keywords):
    if not keywords or text == "":
        return text

    # Convertir en string au cas où ce serait autre chose
    text = str(text)

    for word in keywords:
        if word.strip():
            # Échapper les caractères spéciaux pour la regex
            escaped_word = re.escape(word.strip())
            regex = re.compile(rf"({escaped_word})", re.IGNORECASE)
            # Utiliser des guillemets doubles et échapper le contenu HTML
            text = regex.sub(
                lambda m: f'<span style="background-color:#00e1c6;color:#000;font-weight:600;border-radius:4px;padding:2px 4px;display:inline-block;">{m.group(1)}</span>',
                text,
            )
    return text


# === COLONNES D'AFFICHAGE ===
def format_display_columns(df):
    """
    Formate le DataFrame avec les colonnes demandées pour l'affichage et l'export
    """
    display_df = pd.DataFrame()

    # Ajouter l'ID en première colonne si disponible
    if "id" in df.columns:
        display_df["ID"] = df["id"]

    # Mapping des colonnes selon l'image fournie
    column_mapping = {
        "Article Public Author Title": "title" if "title" in df.columns else None,
        "Journal": "journal" if "journal" in df.columns else None,
        "ISSN": "issn" if "issn" in df.columns else None,
        "DOI": "doi" if "doi" in df.columns else None,
        "URL": "url" if "url" in df.columns else None,
        "Abstract Note": "abstract" if "abstract" in df.columns else None,
        "ABS LO UO": "abs_lo_uo" if "abs_lo_uo" in df.columns else None,
        "Notes": "notes" if "notes" in df.columns else None,
        "Type revue": "type_revue" if "type_revue" in df.columns else None,
        "WL = mesure": "wl_mesure" if "wl_mesure" in df.columns else None,
        "Chir = participants": (
            "chir_participants" if "chir_participants" in df.columns else None
        ),
        "Specialiste": "specialiste" if "specialiste" in df.columns else None,
        "Intervention": "intervention" if "intervention" in df.columns else None,
        "Technique": "technique" if "technique" in df.columns else None,
        "Contexte": "contexte" if "contexte" in df.columns else None,
        "Simulation": "simulation" if "simulation" in df.columns else None,
        "additional outcomes / exclusion": (
            "additional_outcomes" if "additional_outcomes" in df.columns else None
        ),
    }

    # Créer le DataFrame d'affichage avec les colonnes dans l'ordre souhaité
    for display_col, source_col in column_mapping.items():
        if source_col and source_col in df.columns:
            display_df[display_col] = df[source_col]
        else:
            # Ajouter une colonne vide si la colonne n'existe pas
            display_df[display_col] = ""

    # Préserver l'index original pour la correspondance
    display_df.index = df.index

    return display_df


# === EXPORT ===
def export_excel(sub_df, filename):
    # Formater les colonnes pour l'export
    formatted_df = format_display_columns(sub_df)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        formatted_df.to_excel(writer, index=False, sheet_name="Articles")
        worksheet = writer.sheets["Articles"]
        for col_cells in worksheet.columns:
            max_length = 0
            col = col_cells[0].column_letter
            for cell in col_cells:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            worksheet.column_dimensions[col].width = min(
                max_length + 2, 50,
            )  # Limiter la largeur max à 50
    output.seek(0)
    st.download_button(
        f"⬇️ Exporter {filename}",
        output.getvalue(),
        file_name=f"{filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# === APP CONFIG ===
st.set_page_config(
    page_title="NeuroScience Literature Triager", page_icon="🧠", layout="wide",
)

# === CSS ===
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

* { 
    font-family: 'Inter', sans-serif; 
    scroll-behavior: smooth;
}

:root {
    --neuro-primary: #00d4aa;
    --neuro-secondary: #0099ff;
    --neuro-accent: #ff6b9d;
    --neuro-dark: #0a0e27;
    --neuro-darker: #050815;
    --neuro-light: #1a1f3a;
    --neuro-glow: #00f5d4;
    --neuro-warning: #ffa726;
    --neuro-error: #ff5252;
    --neuro-text: #e8eaed;
    --neuro-muted: #9aa0a6;
}

/* Animations neurales */
@keyframes pulse-neural {
    0%, 100% { opacity: 0.6; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.05); }
}

@keyframes float-brain {
    0%, 100% { transform: translateY(0px) rotate(15deg); }
    50% { transform: translateY(-10px) rotate(15deg); }
}

@keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(0, 245, 212, 0.3); }
    50% { box-shadow: 0 0 40px rgba(0, 245, 212, 0.6); }
}

/* Header avec cerveau neural */
.main-header {
    background: linear-gradient(135deg, var(--neuro-darker) 0%, var(--neuro-dark) 30%, #1a237e 70%, #3949ab 100%);
    padding: 50px 40px;
    margin: -1rem -1rem 40px -1rem;
    color: var(--neuro-text);
    width: calc(100% + 2rem);
    position: relative;
    overflow: hidden;
    border-bottom: 3px solid var(--neuro-primary);
    box-shadow: 0 8px 32px rgba(0, 212, 170, 0.2);
}
.st-emotion-cache-18kf3ut{
width: 90% !important;
margin: 0 auto !important;
padding: 0 !important;
}

.st-emotion-cache-zy6yx3{
    padding: 0 !important;
}

.main-header::before {
    content: '';
    position: absolute;
    top: 0%;
    right: 5%;
    width: 300px;
    height: 300px;
    background-image: url('https://purepng.com/public/uploads/large/brain-outline-i4u.png');
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
    opacity: 0.75;
    filter: invert(1);
    transform: rotate(15deg);
    animation: float-brain 6s ease-in-out infinite;
}

.main-header h1 {
    font-size: 2.8rem;
    font-weight: 700;
    margin: 0;
    background: linear-gradient(45deg, var(--neuro-primary), var(--neuro-secondary), var(--neuro-accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 0 30px rgba(0, 245, 212, 0.3);
    position: relative;
    z-index: 2;
}

.main-header p {
    font-size: 1.2rem;
    margin-top: 10px;
    color: var(--neuro-muted);
    font-weight: 400;
    position: relative;
    z-index: 2;
}

/* Système de grille neural */
.st-emotion-cache-zy6yx3 {
    padding-left: 0rem;
    padding-right: 0rem;
}

.stElementContainer:not(:first-of-type):not(:nth-of-type(2)):not(:last-of-type) {
    width: 90% !important;
    margin: 0 auto !important;
}

.st-emotion-cache-wfksaw {
    align-items: center;
}

/* Footer neural */
.footer {
    background: linear-gradient(135deg, var(--neuro-darker), var(--neuro-dark), #1a237e);
    margin: 80px -1rem -1rem -1rem;
    padding: 30px;
    text-align: center;
    color: var(--neuro-text);
    width: calc(100% + 2rem);
    border-top: 3px solid var(--neuro-primary);
    position: relative;
    overflow: hidden;
}

.footer::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at 50% 50%, rgba(0, 245, 212, 0.1) 0%, transparent 70%);
    pointer-events: none;
}

/* Conteneur principal neural */
.main-content {
    width: 90%;
    margin: 0 auto;
    padding: 0;
    position: relative;
}

/* Cartes d'articles neurales */
.article-card {
    background: linear-gradient(145deg, var(--neuro-dark), var(--neuro-light));
    border-radius: 24px;
    padding: 35px;
    margin: 30px auto;
    max-width: 950px;
    border: 2px solid var(--neuro-primary);
    box-shadow: 
        0 20px 40px rgba(0, 0, 0, 0.3),
        0 0 0 1px rgba(0, 245, 212, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
}

.article-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--neuro-primary), var(--neuro-secondary), var(--neuro-accent));
    animation: pulse-neural 3s ease-in-out infinite;
}

.article-card:hover {
    transform: translateY(-5px);
    box-shadow: 
        0 25px 50px rgba(0, 0, 0, 0.4),
        0 0 0 1px rgba(0, 245, 212, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.card-title {
    font-size: 1.6rem;
    font-weight: 600;
    color: var(--neuro-text) !important;
    margin-bottom: 25px;
    line-height: 1.4;
}

/* Méta-données neurales */
.meta-item {
    background: rgba(0, 212, 170, 0.08);
    border: 1px solid rgba(0, 212, 170, 0.2);
    padding: 15px;
    border-radius: 12px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
    backdrop-filter: blur(10px);
}

.meta-item:hover {
    background: rgba(0, 212, 170, 0.12);
    border-color: rgba(0, 212, 170, 0.4);
    transform: translateX(5px);
}

.meta-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--neuro-primary);
    margin-bottom: 5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.meta-value {
    color: var(--neuro-text);
    font-weight: 400;
    line-height: 1.5;
}

/* Section résumé neural */
.abstract-section {
    background: linear-gradient(135deg, #ffffff, #f8f9fa);
    color: #1a1a1a;
    padding: 25px;
    border-radius: 16px;
    margin-top: 20px;
    border: 2px solid var(--neuro-primary);
    box-shadow: 
        0 10px 25px rgba(0, 212, 170, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.8);
    position: relative;
}

.abstract-section strong {
    color: var(--neuro-dark);
    font-weight: 600;
}

/* Liens neuraux */
.st-emotion-cache-r44huj a {
    color: var(--neuro-secondary) !important;
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: all 0.2s ease;
}

.st-emotion-cache-r44huj a:hover {
    color: var(--neuro-primary) !important;
    border-bottom-color: var(--neuro-primary);
}

.st-emotion-cache-tn0cau {
    align-items: center;
}

/* Boutons neuraux */
.stButton > button {
    background: linear-gradient(135deg, var(--neuro-primary), var(--neuro-secondary)) !important;
    border: none !important;
    border-radius: 12px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(0, 212, 170, 0.3) !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(0, 212, 170, 0.4) !important;
    animation: glow-pulse 1s ease-in-out !important;
}

/* Métriques neurales */
.metric-container {
    background: linear-gradient(145deg, var(--neuro-dark), var(--neuro-light));
    border-radius: 16px;
    padding: 20px;
    border: 1px solid var(--neuro-primary);
    text-align: center;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.metric-container::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--neuro-primary), var(--neuro-accent));
}

.metric-container:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 25px rgba(0, 212, 170, 0.2);
}

/* Graphiques neuraux */
.js-plotly-plot {
    border-radius: 16px !important;
    overflow: hidden !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2) !important;
    border: 1px solid rgba(0, 212, 170, 0.2) !important;
}

/* Barres de progression neurales */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--neuro-primary), var(--neuro-secondary)) !important;
    border-radius: 10px !important;
    box-shadow: 0 0 15px rgba(0, 245, 212, 0.4) !important;
}

/* Responsive neural */
@media (max-width: 768px) {
    .main-content {
        width: 95%;
    }
    
    .main-header {
        padding: 40px 20px;
    }
    
    .main-header h1 {
        font-size: 2.2rem;
    }
    
    .main-header::before {
        width: 200px;
        height: 200px;
        top: -10%;
        right: -10%;
    }
    
    .footer {
        padding: 25px 15px;
    }
    
    .article-card {
        padding: 25px;
        margin: 20px auto;
    }
}

/* Effets de glow pour les éléments interactifs */
.stSelectbox > div > div,
.stTextInput > div > div,
.stNumberInput > div > div {
    border-radius: 12px !important;
    border: 1px solid var(--neuro-primary) !important;
    color: var(--neuro-text) !important;
}

.stSelectbox > div > div:focus,
.stTextInput > div > div:focus,
.stNumberInput > div > div:focus {
    box-shadow: 0 0 0 2px var(--neuro-primary) !important;
    border-color: var(--neuro-glow) !important;
}

/* Tables neurales */
.stDataFrame {
    border-radius: 16px !important;
    overflow: hidden !important;
    border: 2px solid var(--neuro-primary) !important;
    box-shadow: 0 8px 25px rgba(0, 212, 170, 0.1) !important;
}

/* Messages neuraux */
.stAlert {
    border-radius: 12px !important;
    border-left: 4px solid var(--neuro-primary) !important;
    background: rgba(0, 212, 170, 0.1) !important;
    backdrop-filter: blur(10px) !important;
}

/* Sidebar neural si présent */
.css-1d391kg {
    background: linear-gradient(180deg, var(--neuro-darker), var(--neuro-dark)) !important;
    border-right: 2px solid var(--neuro-primary) !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# === HEADER ===
st.markdown(
    """
<div class="main-header">
  <h1>🧠 NeuroScience Literature Triager</h1>
  <p>Analyse, tri et sauvegarde des articles scientifiques</p>
</div>
""",
    unsafe_allow_html=True,
)

# Début du conteneur principal centré
st.markdown('<div class="main-content">', unsafe_allow_html=True)


# === GESTION DE SESSION ===
def initialize_session():
    """Initialise les variables de session avec persistance"""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "remember_login" not in st.session_state:
        st.session_state["remember_login"] = False
    if "login_time" not in st.session_state:
        st.session_state["login_time"] = None

    # Vérifier la persistance via query params (simulation de cookies)
    query_params = st.query_params
    if "auth_token" in query_params and "username" in query_params:
        # Simple vérification de token (dans un vrai système, utiliser JWT)
        token = query_params["auth_token"]
        username = query_params["username"]
        if token == f"auth_{username}_token" and not st.session_state["logged_in"]:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["remember_login"] = True
            st.session_state["login_time"] = datetime.now()


def set_persistent_login(username):
    """Configure la persistance de connexion"""
    if st.session_state.get("remember_login", False):
        # Ajouter un token dans l'URL pour simuler la persistance
        st.query_params["auth_token"] = f"auth_{username}_token"
        st.query_params["username"] = username


def logout_user():
    """Déconnecte l'utilisateur et nettoie la session"""
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.session_state["remember_login"] = False
    st.session_state["login_time"] = None

    # Nettoyer les query params pour la persistance
    if "auth_token" in st.query_params:
        del st.query_params["auth_token"]
    if "username" in st.query_params:
        del st.query_params["username"]

    # Nettoyer d'autres variables de session si nécessaire
    if "triage_index" in st.session_state:
        del st.session_state["triage_index"]
    if "excel_data" in st.session_state:
        del st.session_state["excel_data"]


# Initialiser la session
initialize_session()

# === LOGIN ===
if not st.session_state["logged_in"]:
    col_login1, col_login2, col_login3 = st.columns([1, 2, 1])

    with col_login2:
        st.markdown(
            """
        <div style="background: linear-gradient(145deg,#1a1a2e,#16213e); 
                    padding: 40px; border-radius: 20px; border: 1px solid rgba(0,225,198,0.3);
                    box-shadow: 0 15px 35px rgba(0,0,0,0.4); text-align: center;">
            <h2 style="color: #00e1c6; margin-bottom: 30px;">🔐 Connexion</h2>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        username = st.text_input(
            "👤 Nom d'utilisateur", placeholder="Entrez votre nom d'utilisateur",
        )
        password = st.text_input(
            "🔒 Mot de passe", type="password", placeholder="Entrez votre mot de passe",
        )

        col_check, col_btn = st.columns([1, 1])
        with col_check:
            remember = st.checkbox(
                "🔄 Se souvenir de moi", help="Garde la session active plus longtemps",
            )

        with col_btn:
            if st.button("🚀 Se connecter", type="primary", use_container_width=True):
                if username and password:
                    if check_user(username, password):
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = username
                        st.session_state["remember_login"] = remember
                        st.session_state["login_time"] = datetime.now()

                        # Configurer la persistance si demandée
                        if remember:
                            set_persistent_login(username)

                        st.success("✅ Connexion réussie !")
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects")
                else:
                    st.warning("⚠️ Veuillez remplir tous les champs")

    st.stop()

# === APP PRINCIPALE ===
# Header avec info utilisateur et bouton déconnexion
col_user1, col_user2, col_user3 = st.columns([2, 1, 1])

with col_user1:
    login_duration = (
        datetime.now() - st.session_state["login_time"]
        if st.session_state["login_time"]
        else timedelta(0)
    )
    duration_str = str(login_duration).split(".")[0]
    st.success(
        f"👋 Bonjour **{st.session_state['username']}** • ⏱️ Connecté depuis {duration_str}",
    )

with col_user2:
    if st.session_state.get("remember_login", False):
        st.info("🔄 Session mémorisée")
    else:
        st.warning("⚠️ Session temporaire")

with col_user3:
    if st.button(
        "🚪 Se déconnecter",
        type="secondary",
        help="Déconnexion et nettoyage de la session",
    ):
        logout_user()
        st.success("👋 À bientôt !")

# Charger data depuis la BDD directement pour l'utilisateur connecté
df_db = fetch_articles_from_db(st.session_state["username"])

# Upload Excel en plus (optionnel)
uploaded_file = st.file_uploader(
    "📂 Importez un fichier Excel (optionnel)", type=["xlsx", "xlsm"],
)
if uploaded_file:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df["vote_status"] = "pending"
    st.session_state["excel_data"] = df
else:
    df = st.session_state.get("excel_data", None)

# Tri interactif si Excel chargé
if df is not None and len(df[df["vote_status"] == "pending"]) > 0:
    column_mapping = smart_column_mapping(df)
    pending = df[df["vote_status"] == "pending"].reset_index()

    # Navigation et mots-clés
    col_nav1, col_nav2 = st.columns([2, 1])
    with col_nav1:
        keywords_input = st.text_input("🔍 Mots-clés à surligner", "")
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

    with col_nav2:
        total_pending = len(pending)
        current_index = st.session_state.get("triage_index", 0)

        # Input pour aller directement à un article
        target_article = st.number_input(
            f"📍 Aller à l'article (1-{total_pending})",
            min_value=1,
            max_value=total_pending,
            value=current_index + 1,
            key="article_navigator",
        )

        if st.button("📍 Y aller"):
            st.session_state["triage_index"] = target_article - 1

    cur = st.session_state.get("triage_index", 0)

    # S'assurer qu'on ne dépasse pas le nombre d'articles disponibles
    if cur >= len(pending):
        cur = 0
        st.session_state["triage_index"] = 0
    row = pending.iloc[cur]
    idx = int(row["index"])
    current_article = df.loc[idx]

    art_data = {
        "title": get_article_field(
            current_article, "title", column_mapping, "Sans titre",
        ),
        "abstract": get_article_field(
            current_article, "abstract", column_mapping, "Résumé non dispo",
        ),
        "authors": get_article_field(
            current_article, "authors", column_mapping, "Auteurs inconnus",
        ),
        "journal": get_article_field(
            current_article, "journal", column_mapping, "Journal inconnu",
        ),
        "year": safe_year_conversion(
            get_article_field(current_article, "year", column_mapping, ""),
        ),
        "doi": get_article_field(
            current_article, "doi", column_mapping, "DOI non dispo",
        ),
        "url": get_article_field(current_article, "url", column_mapping, ""),
        "issn": get_article_field(current_article, "issn", column_mapping, ""),
        "abs_lo_uo": get_article_field(
            current_article, "abs_lo_uo", column_mapping, "",
        ),
        "notes": get_article_field(current_article, "notes", column_mapping, ""),
        "type_revue": get_article_field(
            current_article, "type_revue", column_mapping, "",
        ),
        "wl_mesure": get_article_field(
            current_article, "wl_mesure", column_mapping, "",
        ),
        "chir_participants": get_article_field(
            current_article, "chir_participants", column_mapping, "",
        ),
        "specialiste": get_article_field(
            current_article, "specialiste", column_mapping, "",
        ),
        "intervention": get_article_field(
            current_article, "intervention", column_mapping, "",
        ),
        "technique": get_article_field(
            current_article, "technique", column_mapping, "",
        ),
        "contexte": get_article_field(current_article, "contexte", column_mapping, ""),
        "simulation": get_article_field(
            current_article, "simulation", column_mapping, "",
        ),
        "additional_outcomes": get_article_field(
            current_article, "additional_outcomes", column_mapping, "",
        ),
    }

    display_data = {k: highlight_text(v, keywords) for k, v in art_data.items()}

    # Affichage de la progression
    progress_pct = (cur + 1) / len(df)
    st.markdown(f"### Article {cur+1}/{len(df)}")
    st.progress(
        progress_pct, text=f"Progression du tri: {cur+1}/{len(df)} ({progress_pct:.1%})",
    )

    st.markdown(
        f"""
    <div class="article-card">
      <h3 class="card-title">📄 {display_data['title']}</h3>
      <div class="meta-item"><div class="meta-label">👥 Auteurs</div><div class="meta-value">{display_data['authors']}</div></div>
      <div class="meta-item"><div class="meta-label">📚 Journal</div><div class="meta-value">{display_data['journal']}</div></div>
      <div class="meta-item"><div class="meta-label">📅 Année</div><div class="meta-value">{display_data['year']}</div></div>
      <div class="meta-item"><div class="meta-label">🔗 DOI</div><div class="meta-value">{display_data['doi']}</div></div>
      {f'<div class="meta-item"><div class="meta-label">🌍 URL</div><div class="meta-value"><a href="{display_data["url"]}" target="_blank">{display_data["url"]}</a></div></div>' if display_data["url"] else ""}
      <div class="abstract-section"><strong>📝 Résumé</strong><br><br>{display_data['abstract']}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🗑️ REJETER"):
            df.at[idx, "vote_status"] = "reject"
            insert_article_in_db(art_data, "reject", st.session_state["username"])
            st.session_state["triage_index"] = cur + 1
    with col2:
        if st.button("⏸️ METTRE DE CÔTÉ"):
            df.at[idx, "vote_status"] = "aside"
            insert_article_in_db(art_data, "aside", st.session_state["username"])
            st.session_state["triage_index"] = cur + 1
    with col3:
        if st.button("✅ GARDER"):
            df.at[idx, "vote_status"] = "accept"
            insert_article_in_db(art_data, "accept", st.session_state["username"])
            st.session_state["triage_index"] = cur + 1

# Toujours afficher les résultats depuis la BDD
st.subheader("📊 Résultats enregistrés en base")

if not df_db.empty:
    kept = df_db[df_db["status"] == "accept"]
    rejected = df_db[df_db["status"] == "reject"]
    aside = df_db[df_db["status"] == "aside"]

    # Fonction pour gérer les modifications et suppressions d'un tableau
    def handle_table_actions(edited_df, original_df, status_name):
        # Suppressions
        delete_col = "🗑️ Supprimer"
        if delete_col in edited_df.columns:
            to_delete = edited_df[edited_df[delete_col]]
            for _, row in to_delete.iterrows():
                if "ID" in row:
                    delete_article_from_db(row["ID"])
                    st.toast(f"🗑️ Article ID {row['ID']} supprimé", icon="🗑️")
            if not to_delete.empty:
                st.rerun()

        # Retirer la colonne de suppression pour la comparaison
        if delete_col in edited_df.columns:
            edited_df = edited_df.drop(columns=[delete_col])
            original_df = original_df.drop(columns=[delete_col])

        if not edited_df.equals(original_df):
            st.success(f"📝 Modifications détectées dans {status_name}")

            # Comparer ligne par ligne pour identifier les changements
            for idx in range(len(edited_df)):
                if idx < len(original_df):
                    original_row = original_df.iloc[idx]
                    edited_row = edited_df.iloc[idx]

                    # Si c'est une ligne modifiée
                    if not edited_row.equals(original_row):
                        # Récupérer l'ID directement depuis la colonne ID du tableau édité
                        if "ID" in edited_df.columns:
                            article_id = edited_row["ID"]
                        else:
                            st.error("Impossible de trouver l'ID de l'article")
                            continue

                        # Préparer les données à mettre à jour (mapping inverse)
                        update_data = {}
                        column_mapping_reverse = {
                            "Article Public Author Title": "title",
                            "Journal": "journal",
                            "ISSN": "issn",
                            "DOI": "doi",
                            "URL": "url",
                            "Abstract Note": "abstract",
                            "ABS LO UO": "abs_lo_uo",
                            "Notes": "notes",
                            "Type revue": "type_revue",
                            "WL = mesure": "wl_mesure",
                            "Chir = participants": "chir_participants",
                            "Specialiste": "specialiste",
                            "Intervention": "intervention",
                            "Technique": "technique",
                            "Contexte": "contexte",
                            "Simulation": "simulation",
                            "additional outcomes / exclusion": "additional_outcomes",
                        }

                        for display_col, db_col in column_mapping_reverse.items():
                            if display_col in edited_df.columns:
                                update_data[db_col] = edited_row[display_col]

                        # Mettre à jour en base
                        try:
                            update_article_in_db(article_id, update_data)
                            st.toast(
                                f"✅ Article ID {article_id} mis à jour", icon="✅",
                            )
                        except Exception as e:
                            st.error(
                                f"Erreur lors de la mise à jour de l'article ID {article_id}: {e}",
                            )

    st.markdown("### ✅ Conservés")
    if len(kept) > 0:
        kept_display = format_display_columns(kept)
        kept_display["🗑️ Supprimer"] = False

        # Configuration des colonnes - ID en lecture seule
        column_config = {}
        if "ID" in kept_display.columns:
            column_config["ID"] = st.column_config.NumberColumn(
                "ID",
                help="ID unique de l'article (non modifiable)",
                disabled=True,
                width="small",
            )
        column_config["🗑️ Supprimer"] = st.column_config.CheckboxColumn(
            "🗑️", help="Supprimer l'article",
        )

        edited_kept = st.data_editor(
            kept_display,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            key="kept_editor",
        )
        handle_table_actions(edited_kept, kept_display, "articles conservés")
    else:
        st.info("Aucun article conservé.")

    st.markdown("### ❌ Rejetés")
    if len(rejected) > 0:
        rejected_display = format_display_columns(rejected)
        rejected_display["🗑️ Supprimer"] = False

        # Configuration des colonnes - ID en lecture seule
        column_config = {}
        if "ID" in rejected_display.columns:
            column_config["ID"] = st.column_config.NumberColumn(
                "ID",
                help="ID unique de l'article (non modifiable)",
                disabled=True,
                width="small",
            )
        column_config["🗑️ Supprimer"] = st.column_config.CheckboxColumn(
            "🗑️", help="Supprimer l'article",
        )

        edited_rejected = st.data_editor(
            rejected_display,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            key="rejected_editor",
        )
        handle_table_actions(edited_rejected, rejected_display, "articles rejetés")
    else:
        st.info("Aucun article rejeté.")

    st.markdown("### ⏸️ Mis de côté")
    if len(aside) > 0:
        aside_display = format_display_columns(aside)
        aside_display["🗑️ Supprimer"] = False

        # Configuration des colonnes - ID en lecture seule
        column_config = {}
        if "ID" in aside_display.columns:
            column_config["ID"] = st.column_config.NumberColumn(
                "ID",
                help="ID unique de l'article (non modifiable)",
                disabled=True,
                width="small",
            )
        column_config["🗑️ Supprimer"] = st.column_config.CheckboxColumn(
            "🗑️", help="Supprimer l'article",
        )

        edited_aside = st.data_editor(
            aside_display,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            key="aside_editor",
        )
        handle_table_actions(edited_aside, aside_display, "articles mis de côté")
    else:
        st.info("Aucun article mis de côté.")

    # Boutons d'export (utilisent les données actuelles de la base)
    st.markdown("### 📤 Export")
    col_exp = st.columns(3)
    with col_exp[0]:
        if len(kept) > 0:
            export_excel(kept, "articles_conserves")
    with col_exp[1]:
        if len(rejected) > 0:
            export_excel(rejected, "articles_supprimes")
    with col_exp[2]:
        if len(aside) > 0:
            export_excel(aside, "articles_mis_de_cote")

    if st.button("🔄 Actualiser les données"):
        st.toast("Données actualisées", icon="🔄")
else:
    st.info("Aucun article trié en base de données.")

# === SECTION STATISTIQUES ===
if not df_db.empty:
    st.markdown("---")
    st.markdown("### 📊 Statistiques et Analytics")

    # Préparer les données
    df_stats = df_db.copy()

    # Convertir date_action en datetime si ce n'est pas déjà fait
    if "date_action" in df_stats.columns:
        df_stats["date_action"] = pd.to_datetime(df_stats["date_action"])
        df_stats["date_only"] = df_stats["date_action"].dt.date

    # Créer 3 colonnes pour les métriques principales
    col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)

    total_articles = len(df_stats)
    kept_count = len(df_stats[df_stats["status"] == "accept"])
    rejected_count = len(df_stats[df_stats["status"] == "reject"])
    aside_count = len(df_stats[df_stats["status"] == "aside"])

    with col_metric1:
        st.metric("📚 Total Articles", total_articles)
    with col_metric2:
        st.metric("✅ Conservés", kept_count, f"{kept_count/total_articles*100:.1f}%")
    with col_metric3:
        st.metric(
            "❌ Rejetés", rejected_count, f"{rejected_count/total_articles*100:.1f}%",
        )
    with col_metric4:
        st.metric("⏸️ En attente", aside_count, f"{aside_count/total_articles*100:.1f}%")

    # Ligne 1: Distribution des statuts + Évolution temporelle
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### 🥧 Répartition par statut")
        status_counts = df_stats["status"].value_counts()
        status_mapping = {
            "accept": "Conservés",
            "reject": "Rejetés",
            "aside": "Mis de côté",
        }

        fig_pie = px.pie(
            values=status_counts.values,
            names=[status_mapping.get(x, x) for x in status_counts.index],
            color_discrete_map={
                "Conservés": "#00e1c6",
                "Rejetés": "#ff6b6b",
                "Mis de côté": "#ffd93d",
            },
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(height=350, showlegend=True)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_chart2:
        if "date_action" in df_stats.columns:
            st.markdown("#### 📈 Évolution du tri par jour")
            daily_stats = (
                df_stats.groupby(["date_only", "status"])
                .size()
                .reset_index(name="count")
            )

            fig_line = px.line(
                daily_stats,
                x="date_only",
                y="count",
                color="status",
                color_discrete_map={
                    "accept": "#00e1c6",
                    "reject": "#ff6b6b",
                    "aside": "#ffd93d",
                },
                title="Articles triés par jour",
            )
            fig_line.update_layout(height=350)
            st.plotly_chart(fig_line, use_container_width=True)

    # Ligne 2: Top Journals + Activité par utilisateur
    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        if "journal" in df_stats.columns and df_stats["journal"].notna().sum() > 0:
            st.markdown("#### 📰 Top 10 Journals")
            top_journals = (
                df_stats[df_stats["journal"].notna()]["journal"].value_counts().head(10)
            )

            fig_bar = px.bar(
                x=top_journals.values,
                y=top_journals.index,
                orientation="h",
                color=top_journals.values,
                color_continuous_scale="viridis",
            )
            fig_bar.update_layout(
                height=350,
                yaxis={"categoryorder": "total ascending"},
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart4:
        if "user" in df_stats.columns:
            st.markdown("#### 👥 Activité par utilisateur")
            user_stats = (
                df_stats.groupby(["user", "status"]).size().reset_index(name="count")
            )

            fig_user = px.bar(
                user_stats,
                x="user",
                y="count",
                color="status",
                color_discrete_map={
                    "accept": "#00e1c6",
                    "reject": "#ff6b6b",
                    "aside": "#ffd93d",
                },
                title="Articles par utilisateur et statut",
            )
            fig_user.update_layout(height=350)
            st.plotly_chart(fig_user, use_container_width=True)

    # Ligne 3: Distribution par année + Spécialités
    col_chart5, col_chart6 = st.columns(2)

    with col_chart5:
        if "year" in df_stats.columns and df_stats["year"].notna().sum() > 0:
            st.markdown("#### 📅 Distribution par année de publication")
            year_data = df_stats[df_stats["year"].notna()]["year"].astype(str)
            year_counts = year_data.value_counts().sort_index()

            fig_year = px.bar(
                x=year_counts.index,
                y=year_counts.values,
                color=year_counts.values,
                color_continuous_scale="plasma",
            )
            fig_year.update_layout(
                height=350,
                xaxis_title="Année",
                yaxis_title="Nombre d'articles",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_year, use_container_width=True)

    with col_chart6:
        if (
            "specialiste" in df_stats.columns
            and df_stats["specialiste"].notna().sum() > 0
        ):
            st.markdown("#### 🏥 Top Spécialités")
            spec_counts = (
                df_stats[df_stats["specialiste"].notna()]["specialiste"]
                .value_counts()
                .head(8)
            )

            fig_spec = px.bar(
                x=spec_counts.index,
                y=spec_counts.values,
                color=spec_counts.values,
                color_continuous_scale="turbo",
            )
            fig_spec.update_layout(
                height=350,
                xaxis_title="Spécialité",
                yaxis_title="Nombre d'articles",
                coloraxis_showscale=False,
                xaxis={"tickangle": 45},
            )
            st.plotly_chart(fig_spec, use_container_width=True)

    # Graphique de synthèse: Heatmap temporelle
    if "date_action" in df_stats.columns:
        st.markdown("#### 🔥 Heatmap de l'activité de tri")

        # Créer des données pour la heatmap
        df_stats["hour"] = df_stats["date_action"].dt.hour
        df_stats["day_name"] = df_stats["date_action"].dt.day_name()

        heatmap_data = (
            df_stats.groupby(["day_name", "hour"]).size().reset_index(name="count")
        )
        heatmap_pivot = heatmap_data.pivot(
            index="day_name", columns="hour", values="count",
        ).fillna(0)

        # Réordonner les jours
        day_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        heatmap_pivot = heatmap_pivot.reindex(
            [day for day in day_order if day in heatmap_pivot.index],
        )

        fig_heatmap = px.imshow(
            heatmap_pivot,
            color_continuous_scale="viridis",
            aspect="auto",
            labels=dict(x="Heure", y="Jour", color="Articles triés"),
        )
        fig_heatmap.update_layout(height=300)
        st.plotly_chart(fig_heatmap, use_container_width=True)

# Fin du conteneur principal centré
st.markdown("</div>", unsafe_allow_html=True)

# === FOOTER ===
st.markdown(
    """
<div class="footer">
  🧠 NeuroScience Literature Triager – v3 avec persistance MySQL
</div>
""",
    unsafe_allow_html=True,
)
