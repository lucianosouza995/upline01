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
# ... (código existente para gestão de clientes, elevadores, tecnicos) ...

@app.route('/admin/chamados', methods=['GET'])
def get_todos_chamados():
    query = Chamado.query

    # Filtros
    cliente_id = request.args.get('cliente_id')
    elevador_id = request.args.get('elevador_id')
    tecnico_id = request.args.get('tecnico_id')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if cliente_id:
        query = query.join(Elevador).filter(Elevador.cliente_id == cliente_id)
    if elevador_id:
        query = query.filter(Chamado.elevador_id == elevador_id)
    if tecnico_id:
        query = query.filter(Chamado.tecnico_id == tecnico_id)
    if data_inicio:
        data_inicio_obj = datetime.datetime.strptime(data_inicio, '%Y-%m-%d')
        query = query.filter(Chamado.timestamp >= data_inicio_obj)
    if data_fim:
        data_fim_obj = datetime.datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Chamado.timestamp <= data_fim_obj)

    chamados = query.order_by(Chamado.timestamp.desc()).all()
    lista_chamados = [{
        'id_chamado': c.id, 'status': c.status,
        'endereco': c.elevador.endereco,
        'tecnico_responsavel': c.tecnico.nome if c.tecnico else 'N/A',
        'data_abertura': c.timestamp.strftime('%d/%m/%Y %H:%M'),
        'data_finalizacao': c.data_finalizacao.strftime('%d/%m/%Y %H:%M') if c.data_finalizacao else None
    } for c in chamados]
    return jsonify(lista_chamados)

# ... (restante do código do backend) ...
