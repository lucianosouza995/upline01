# app.py
# Backend para o sistema de chamados da UpLine Elevadores
# Use os seguintes comandos para instalar as dependências:
# pip install Flask Flask-SQLAlchemy flask-cors psycopg2-binary

import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from math import radians, sin, cos, sqrt, atan2
import datetime
from sqlalchemy import func, extract

# --- CONFIGURAÇÃO INICIAL ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURAÇÃO DA BASE DE DADOS ---
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'upline.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS (ESTRUTURA) ---
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    possui_contrato = db.Column(db.Boolean, default=True)
    elevadores = db.relationship('Elevador', backref='cliente', lazy=True, cascade="all, delete-orphan")

class Elevador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_qr = db.Column(db.String(50), unique=True, nullable=False)
    endereco = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    chamados = db.relationship('Chamado', backref='elevador', lazy=True, cascade="all, delete-orphan")

class Tecnico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    de_plantao = db.Column(db.Boolean, default=False)
    last_latitude = db.Column(db.Float, nullable=True)
    last_longitude = db.Column(db.Float, nullable=True)
    chamados = db.relationship('Chamado', backref='tecnico', lazy=True)

class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    descricao_problema = db.Column(db.String(500), nullable=False)
    pessoa_presa = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='aberto')
    elevador_id = db.Column(db.Integer, db.ForeignKey('elevador.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnico.id'), nullable=True)
    servicos_realizados = db.Column(db.Text, nullable=True)
    pecas_trocadas = db.Column(db.Text, nullable=True)
    observacao_texto = db.Column(db.Text, nullable=True)
    data_finalizacao = db.Column(db.DateTime, nullable=True)

# --- ROTAS PÚBLICAS (Chatbot e App do Técnico) ---
# ... (código existente para rotas públicas) ...

# --- ROTAS DE GESTÃO (ADMIN) ---
# ... (código existente para gestão de clientes, elevadores, tecnicos, chamados) ...

# NOVA ROTA PARA DADOS DO DASHBOARD
@app.route('/admin/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    try:
        # 1. Chamados por Status
        status_counts = db.session.query(Chamado.status, func.count(Chamado.status)).group_by(Chamado.status).all()
        chamados_por_status = {status: count for status, count in status_counts}

        # 2. Chamados por Técnico
        tecnico_counts = db.session.query(Tecnico.nome, func.count(Chamado.id)).join(Chamado, Tecnico.id == Chamado.tecnico_id).group_by(Tecnico.nome).order_by(func.count(Chamado.id).desc()).all()
        chamados_por_tecnico = {nome: count for nome, count in tecnico_counts}

        # 3. Chamados nos últimos 12 meses
        doze_meses_atras = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        chamados_mes = db.session.query(
            extract('year', Chamado.timestamp).label('ano'),
            extract('month', Chamado.timestamp).label('mes'),
            func.count(Chamado.id)
        ).filter(Chamado.timestamp >= doze_meses_atras).group_by('ano', 'mes').order_by('ano', 'mes').all()
        
        chamados_por_mes = [{'mes': f"{int(mes):02d}/{int(ano)}", 'total': total} for ano, mes, total in chamados_mes]

        # 4. Contagens totais
        total_chamados = Chamado.query.count()
        total_tecnicos = Tecnico.query.count()
        total_elevadores = Elevador.query.count()

        return jsonify({
            'total_chamados': total_chamados,
            'total_tecnicos': total_tecnicos,
            'total_elevadores': total_elevadores,
            'chamados_por_status': chamados_por_status,
            'chamados_por_tecnico': chamados_por_tecnico,
            'chamados_por_mes': chamados_por_mes
        })

    except Exception as e:
        app.logger.error(f"Erro ao gerar estatísticas do dashboard: {e}")
        return jsonify({"erro": "Não foi possível carregar as estatísticas."}), 500


# ... (restante do código do backend) ...
