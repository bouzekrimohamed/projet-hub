from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
import datetime as dt_module
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # For session and login
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///suivi_palettes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.String(50), primary_key=True)  # username as id
    password = db.Column(db.String(128))

class Transporteur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Planning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jour = db.Column(db.Integer)
    semaine = db.Column(db.Integer)
    date = db.Column(db.Date)
    heures = db.Column(db.Float)
    type_mvt = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    transporteur = db.Column(db.String(100))
    commentaire = db.Column(db.Text)
    quai = db.Column(db.String(50))
    nb_pals = db.Column(db.Integer)
    heure_arr = db.Column(db.String(50))
    heure_dep = db.Column(db.String(50))
    retard = db.Column(db.Float)

class Entree(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    semaine = db.Column(db.Integer)
    date = db.Column(db.Date)
    transp = db.Column(db.String(100))
    n_bons = db.Column(db.String(100))
    eur = db.Column(db.Integer)
    shep = db.Column(db.Integer)
    lpr = db.Column(db.Integer)
    perdue = db.Column(db.Integer)
    eur_dim = db.Column(db.String(20))
    shep_dim = db.Column(db.String(20))
    lpr_dim = db.Column(db.String(20))
    perdue_dim = db.Column(db.String(20))
    total = db.Column(db.Integer)
    commentaire = db.Column(db.Text)
    type_mvt = db.Column(db.String(50))

class Sortie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    semaine = db.Column(db.Integer)
    date = db.Column(db.Date)
    transp = db.Column(db.String(100))
    n_bons = db.Column(db.String(100))
    eur_rendus = db.Column(db.Integer)
    shep_rendus = db.Column(db.Integer)
    lpr_rendus = db.Column(db.Integer)
    perdue = db.Column(db.Integer)
    eur_dim = db.Column(db.String(20))
    shep_dim = db.Column(db.String(20))
    lpr_dim = db.Column(db.String(20))
    perdue_dim = db.Column(db.String(20))
    total = db.Column(db.Integer)
    commentaire = db.Column(db.Text)
    type_mvt = db.Column(db.String(50))

# Obtenir le jour de la semaine et la semaine ISO
def get_jour_semaine(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        jour = dt.isoweekday()
        semaine = dt.isocalendar().week
        return jour, semaine
    except:
        return "", ""

# Convertir heure décimale en format HH:MM
def decimal_to_time(decimal):
    if decimal is None or decimal == "":
        return ""
    hours = int(decimal * 24)
    minutes = int((decimal * 24 - hours) * 60)
    return f"{hours:02d}:{minutes:02d}"

# Convertir HH:MM en décimal
def time_to_decimal(time_str):
    if not time_str or time_str == "Accroche":
        return 0
    try:
        h, m = map(int, time_str.split(":"))
        return (h + m / 60.0) / 24.0
    except:
        return 0

# Calculer retard
def calculer_retard(heure_planifiee, heure_arrivee):
    if not heure_planifiee or not heure_arrivee or heure_arrivee == "Accroche":
        return 0
    try:
        plan = time_to_decimal(heure_planifiee)
        arr = time_to_decimal(heure_arrivee)
        retard = arr - plan if arr > plan else 0
        return retard
    except:
        return 0

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

# Route principale
@app.route('/')
@login_required
def index():
    current_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', current_date=current_date, username=current_user.id)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.session.get(User, username)
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html', error=None)

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Toggle theme
@app.route('/toggle_theme', methods=['POST'])
def toggle_theme():
    theme = request.json.get('theme')
    session['theme'] = theme
    return jsonify({'success': True})

# API pour enregistrer des données
@app.route('/api/enregistrer', methods=['POST'])
@login_required
def api_enregistrer():
    data = request.json
    date_str = data['date']
    if not date_str or len(date_str) != 10:
        return jsonify({'error': 'Format de date incorrect (AAAA-MM-JJ)'}), 400

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    jour, semaine = get_jour_semaine(date_str)
    transporteur = data['transporteur'].strip()
    if transporteur == "":
        return jsonify({'error': 'Veuillez sélectionner ou entrer un transporteur'}), 400
    if not db.session.query(Transporteur.query.filter_by(name=transporteur).exists()).scalar():
        new_transp = Transporteur(name=transporteur)
        db.session.add(new_transp)
        db.session.commit()

    type_mvt = data['type_mvt']
    reference = data.get('reference', '')
    quai = data.get('quai', '')
    palettes_eur = int(data.get('palettes_eur', 0))
    palettes_shep = int(data.get('palettes_shep', 0))
    palettes_lpr = int(data.get('palettes_lpr', 0))
    palettes_perdues = int(data.get('palettes_perdues', 0))
    eur_dim = data.get('eur_dim', '80x120')
    shep_dim = data.get('shep_dim', '80x120')
    lpr_dim = data.get('lpr_dim', '80x120')
    perdue_dim = data.get('perdue_dim', '80x120')
    total_palettes = palettes_eur + palettes_shep + palettes_lpr + palettes_perdues
    heure_plan = data.get('heure_plan', '')
    heure_arr = data.get('heure_arr', '')
    heure_dep = data.get('heure_dep', '')
    commentaire = data.get('commentaire', '')

    retard = calculer_retard(heure_plan, heure_arr)
    heure_plan_decimal = time_to_decimal(heure_plan)

    try:
        # Enregistrer dans planning
        new_planning = Planning(
            jour=jour, semaine=semaine, date=dt.date(), heures=heure_plan_decimal,
            type_mvt=type_mvt, reference=reference, transporteur=transporteur,
            commentaire=commentaire, quai=quai, nb_pals=total_palettes,
            heure_arr=heure_arr, heure_dep=heure_dep, retard=retard
        )
        db.session.add(new_planning)

        # Enregistrer dans Entree ou Sortie based on type_mvt
        if type_mvt in ["Réception", "Retour"]:
            new_entree = Entree(
                type="ENTREE", semaine=semaine, date=dt.date(), transp=transporteur,
                n_bons=reference, eur=palettes_eur, shep=palettes_shep, lpr=palettes_lpr,
                perdue=palettes_perdues, eur_dim=eur_dim, shep_dim=shep_dim, lpr_dim=lpr_dim,
                perdue_dim=perdue_dim, total=total_palettes, commentaire=commentaire, type_mvt=type_mvt
            )
            db.session.add(new_entree)
        else:
            new_sortie = Sortie(
                type="SORTIE", semaine=semaine, date=dt.date(), transp=transporteur,
                n_bons=reference, eur_rendus=palettes_eur, shep_rendus=palettes_shep,
                lpr_rendus=palettes_lpr, perdue=palettes_perdues, eur_dim=eur_dim,
                shep_dim=shep_dim, lpr_dim=lpr_dim, perdue_dim=perdue_dim,
                total=total_palettes, commentaire=commentaire, type_mvt=type_mvt
            )
            db.session.add(new_sortie)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Enregistrement effectué ✅'})
    except Exception as e:
        db.session.rollback()
        print(f"Erreur enregistrement: {e}")
        return jsonify({'error': str(e)}), 500

# API pour récupérer les données planning avec filtres
@app.route('/api/planning')
@login_required
def api_planning():
    try:
        query = Planning.query

        type_filter = request.args.get('type', '')
        transporteur_filter = request.args.get('transporteur', '')
        date_debut = request.args.get('date_debut', '')
        date_fin = request.args.get('date_fin', '')
        quai_filter = request.args.get('quai', '')

        if type_filter:
            query = query.filter_by(type_mvt=type_filter)
        if transporteur_filter:
            query = query.filter_by(transporteur=transporteur_filter)
        if date_debut:
            query = query.filter(Planning.date >= dt_module.date.fromisoformat(date_debut))
        if date_fin:
            query = query.filter(Planning.date <= dt_module.date.fromisoformat(date_fin))
        if quai_filter:
            query = query.filter_by(quai=quai_filter)

        plannings = query.all()
        data = []
        for p in plannings:
            data.append({
                'Jour': p.jour or '',
                'Semaine': p.semaine or '',
                'Date_str': p.date.strftime('%Y-%m-%d') if p.date else '',
                'Heure_plan': decimal_to_time(p.heures),
                'Expé/Récep': p.type_mvt or '',
                'Référence': p.reference or '',
                'TRANSPORTEUR': p.transporteur or '',
                'COMMENTAIRE': p.commentaire or '',
                'QUAI': p.quai or '',
                'NB Pals Réelles Sol': p.nb_pals or 0,
                'Heure_arr': p.heure_arr or '',
                'Heure_dep': p.heure_dep or '',
                'Retard_str': decimal_to_time(p.retard)
            })
        return jsonify(data)
    except Exception as e:
        print(f"Erreur api_planning: {e}")
        return jsonify({'error': str(e)}), 500

# API pour récupérer Total palettes avec filtres (computé on-the-fly)
@app.route('/api/total_palettes')
@login_required
def api_total_palettes():
    try:
        # Récupérer toutes les dates uniques
        entree_dates = db.session.query(db.distinct(Entree.date)).all()
        sortie_dates = db.session.query(db.distinct(Sortie.date)).all()
        all_dates = sorted(set([d[0] for d in entree_dates + sortie_dates if d[0]]))

        data = []
        stock_cumule = 0
        non_rendus_cumule = 0
        for date in all_dates:
            # Entree
            entree_good = db.session.query(db.func.sum(Entree.eur + Entree.shep + Entree.lpr)).filter(Entree.date == date).scalar() or 0
            non_conf_entree = db.session.query(db.func.sum(Entree.perdue)).filter(Entree.date == date).scalar() or 0
            total_entree = entree_good + non_conf_entree
            entree_first = Entree.query.filter_by(date=date).first()
            semaine_ent = entree_first.semaine if entree_first else date.isocalendar().week

            # Sortie
            sortie_rendus = db.session.query(db.func.sum(Sortie.eur_rendus + Sortie.shep_rendus + Sortie.lpr_rendus)).filter(Sortie.date == date).scalar() or 0
            sortie_perdue = db.session.query(db.func.sum(Sortie.perdue)).filter(Sortie.date == date).scalar() or 0
            total_sortie = sortie_rendus + sortie_perdue
            sortie_first = Sortie.query.filter_by(date=date).first()
            semaine_sort = sortie_first.semaine if sortie_first else date.isocalendar().week

            stock_cumule += total_entree - total_sortie
            non_rendus_day = sortie_perdue  # Assuming non rendus is perdue in sortie
            non_rendus_cumule += non_rendus_day
            retour = sortie_rendus
            pourcentage_retour = (sortie_rendus / total_sortie * 100) if total_sortie > 0 else 0

            row = {
                "Semaine": str(semaine_ent),
                "Date": date.strftime('%Y-%m-%d'),
                "Entrée (EUR + SHEP + LPR)": entree_good,
                "Non Conforme Entrée": non_conf_entree,
                "TOTAL_entree": total_entree,
                "Separator1": "",
                "Semaine_sortie": str(semaine_sort),
                "Date_sortie": date.strftime('%Y-%m-%d'),
                "Rendus (EUR + SHEP + LPR)": sortie_rendus,
                "Non Rendus": non_rendus_day,
                "TOTAL_sortie": total_sortie,
                "Separator2": "",
                "Stock_Sur_QUAI": stock_cumule,
                "Non Rendus Cumulé": non_rendus_cumule,
                "RETOUR": retour,
                "Pourcentage_Retour": f"{pourcentage_retour:.2f}%"
            }
            data.append(row)

        # Filtres
        semaine_filter = request.args.get('semaine', '')
        date_debut = request.args.get('date_debut', '')
        date_fin = request.args.get('date_fin', '')

        if semaine_filter:
            data = [r for r in data if r['Semaine'] == str(semaine_filter)]
        if date_debut:
            date_debut_dt = dt_module.date.fromisoformat(date_debut)
            data = [r for r in data if dt_module.date.fromisoformat(r['Date']) >= date_debut_dt]
        if date_fin:
            date_fin_dt = dt_module.date.fromisoformat(date_fin)
            data = [r for r in data if dt_module.date.fromisoformat(r['Date']) <= date_fin_dt]

        return jsonify(data)
    except Exception as e:
        print(f"Erreur api_total_palettes: {e}")
        return jsonify({'error': str(e)}), 500

# API pour récupérer Entrée avec filtres
@app.route('/api/entree')
@login_required
def api_entree():
    try:
        query = Entree.query

        transporteur_filter = request.args.get('transporteur', '')
        date_debut = request.args.get('date_debut', '')
        date_fin = request.args.get('date_fin', '')

        if transporteur_filter:
            query = query.filter_by(transp=transporteur_filter)
        if date_debut:
            query = query.filter(Entree.date >= dt_module.date.fromisoformat(date_debut))
        if date_fin:
            query = query.filter(Entree.date <= dt_module.date.fromisoformat(date_fin))

        entrees = query.all()
        data = []
        for e in entrees:
            data.append({
                'Type': e.type or '',
                'Semaine': e.semaine or '',
                'Date': e.date.strftime('%Y-%m-%d') if e.date else '',
                'Transp': e.transp or '',
                'N° Bons': e.n_bons or '',
                'EUR': e.eur or 0,
                'EUR Dim': e.eur_dim or '',
                'SHEP': e.shep or 0,
                'SHEP Dim': e.shep_dim or '',
                'LPR': e.lpr or 0,
                'LPR Dim': e.lpr_dim or '',
                'PERDUE': e.perdue or 0,
                'PERDUE Dim': e.perdue_dim or '',
                'TOTAL': e.total or 0,
                'Commentaire': e.commentaire or ''
            })
        return jsonify(data)
    except Exception as e:
        print(f"Erreur api_entree: {e}")
        return jsonify({'error': str(e)}), 500

# API pour récupérer Sortie avec filtres
@app.route('/api/sortie')
@login_required
def api_sortie():
    try:
        query = Sortie.query

        transporteur_filter = request.args.get('transporteur', '')
        date_debut = request.args.get('date_debut', '')
        date_fin = request.args.get('date_fin', '')

        if transporteur_filter:
            query = query.filter_by(transp=transporteur_filter)
        if date_debut:
            query = query.filter(Sortie.date >= dt_module.date.fromisoformat(date_debut))
        if date_fin:
            query = query.filter(Sortie.date <= dt_module.date.fromisoformat(date_fin))

        sorties = query.all()
        data = []
        for s in sorties:
            data.append({
                'Type': s.type or '',
                'Semaine': s.semaine or '',
                'Date': s.date.strftime('%Y-%m-%d') if s.date else '',
                'Transp': s.transp or '',
                'N° Bons': s.n_bons or '',
                'EUR Rendus': s.eur_rendus or 0,
                'EUR Dim': s.eur_dim or '',
                'SHEP Rendus': s.shep_rendus or 0,
                'SHEP Dim': s.shep_dim or '',
                'LPR Rendus': s.lpr_rendus or 0,
                'LPR Dim': s.lpr_dim or '',
                'PERDUE': s.perdue or 0,
                'PERDUE Dim': s.perdue_dim or '',
                'TOTAL': s.total or 0,
                'Commentaire': s.commentaire or ''
            })
        return jsonify(data)
    except Exception as e:
        print(f"Erreur api_sortie: {e}")
        return jsonify({'error': str(e)}), 500

# API pour récupérer la liste des transporteurs
@app.route('/api/transporteurs')
@login_required
def api_transporteurs():
    transporteurs = [t.name for t in Transporteur.query.order_by(Transporteur.name).all()]
    return jsonify(transporteurs)

# API pour stats
@app.route('/api/stats')
@login_required
def api_stats():
    try:
        total_palettes = db.session.query(db.func.sum(Planning.nb_pals)).scalar() or 0
        total_retard = db.session.query(db.func.sum(Planning.retard)).scalar() or 0.0
        count_planning = db.session.query(db.func.count(Planning.id)).scalar()
        average_retard = total_retard / count_planning if count_planning > 0 else 0.0
        total_eur_entree = db.session.query(db.func.sum(Entree.eur)).scalar() or 0
        total_shep_entree = db.session.query(db.func.sum(Entree.shep)).scalar() or 0
        total_lpr_entree = db.session.query(db.func.sum(Entree.lpr)).scalar() or 0
        total_perdues_entree = db.session.query(db.func.sum(Entree.perdue)).scalar() or 0
        total_eur_sortie = db.session.query(db.func.sum(Sortie.eur_rendus)).scalar() or 0
        total_shep_sortie = db.session.query(db.func.sum(Sortie.shep_rendus)).scalar() or 0
        total_lpr_sortie = db.session.query(db.func.sum(Sortie.lpr_rendus)).scalar() or 0
        total_perdues_sortie = db.session.query(db.func.sum(Sortie.perdue)).scalar() or 0

        recommendation = "Optimiser le transport" if (total_perdues_entree + total_perdues_sortie) > (total_palettes * 0.1) else "Tout va bien"

        # Calcul des soldes
        partners = [t.name for t in Transporteur.query.all()]
        balances = {}
        for partner in partners:
            received = db.session.query(db.func.sum(Entree.eur + Entree.shep + Entree.lpr)).filter(Entree.transp == partner, Entree.type_mvt.in_(["Réception", "Retour"])).scalar() or 0
            returned = db.session.query(db.func.sum(Sortie.eur_rendus + Sortie.shep_rendus + Sortie.lpr_rendus)).filter(Sortie.transp == partner, Sortie.type_mvt.in_(["Expédition", "Restitution"])).scalar() or 0
            if partner in ["Lagny", "Soissons"]:
                balances[partner] = received - returned  # owed_to if positive
            else:
                balances[partner] = returned - received  # owed_from if positive, but adjust sign

        owed_to = {p: b for p, b in balances.items() if p in ["Lagny", "Soissons"] and b > 0}
        owed_from = {p: abs(b) for p, b in balances.items() if p not in ["Lagny", "Soissons"] and b < 0}

        data = {
            'total_palettes': int(total_palettes),
            'total_retard': float(total_retard),
            'average_retard': float(average_retard),
            'total_eur_entree': int(total_eur_entree),
            'total_shep_entree': int(total_shep_entree),
            'total_lpr_entree': int(total_lpr_entree),
            'total_perdues_entree': int(total_perdues_entree),
            'total_eur_sortie': int(total_eur_sortie),
            'total_shep_sortie': int(total_shep_sortie),
            'total_lpr_sortie': int(total_lpr_sortie),
            'total_perdues_sortie': int(total_perdues_sortie),
            'recommendation': recommendation,
            'owed_to': owed_to,
            'owed_from': owed_from
        }
        return jsonify(data)
    except Exception as e:
        print(f"Erreur api_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/export')
@login_required
def export():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Planning
        df_planning = pd.read_sql(db.session.query(Planning).statement, db.session.bind)
        df_planning.to_excel(writer, sheet_name='planning', index=False)

        # Entree
        df_entree = pd.read_sql(db.session.query(Entree).statement, db.session.bind)
        df_entree.to_excel(writer, sheet_name='Entree', index=False)

        # Sortie
        df_sortie = pd.read_sql(db.session.query(Sortie).statement, db.session.bind)
        df_sortie.to_excel(writer, sheet_name='Sortie', index=False)

        # Total palettes (from API logic)
        data = api_total_palettes().get_json()
        df_total = pd.DataFrame(data)
        df_total.to_excel(writer, sheet_name='Total palettes', index=False)

    output.seek(0)
    return send_file(output, attachment_filename='suivi_palettes.xlsx', as_attachment=True)

def init_data():
    if not db.session.get(User, 'OTC-HUB-HTS3'):
        users_data = {
            'OTC-HUB-HTS3': 'MOMO123.',
            'user2': 'pass2',
            'user3': 'pass3'
        }
        for username, password in users_data.items():
            hashed_pw = generate_password_hash(password)
            user = User(id=username, password=hashed_pw)
            db.session.add(user)

        initial_transp = ["LOGITRANS", "TLOT", "LAMART", "Retour MTS", "Lagny", "Soissons"]
        for name in initial_transp:
            transp = Transporteur(name=name)
            db.session.add(transp)

        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_data()
    
    import os
    port = int(os.environ.get("PORT", 5000))  # Render va injecter le bon port
    app.run(host="0.0.0.0", port=port, debug=False)