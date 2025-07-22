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
@app.route('/')
def index():
    return "API da UpLine Elevadores está no ar!"

# --- ROTAS DE GESTÃO (ADMIN) ---
# ... (código existente para gestão de clientes, elevadores) ...

@app.route('/admin/tecnicos', methods=['GET', 'POST'])
def gerir_tecnicos():
    if request.method == 'GET':
        tecnicos = Tecnico.query.order_by(Tecnico.id).all()
        # Adicionado 'de_plantao' ao retorno
        return jsonify([{'id': t.id, 'nome': t.nome, 'username': t.username, 'de_plantao': t.de_plantao} for t in tecnicos])
    elif request.method == 'POST':
        dados = request.json
        novo_tecnico = Tecnico(nome=dados['nome'], username=dados['username'], password=dados['password'])
        db.session.add(novo_tecnico)
        db.session.commit()
        return jsonify({'id': novo_tecnico.id, 'nome': novo_tecnico.nome}), 201

# NOVA ROTA PARA ATUALIZAR STATUS DE PLANTÃO
@app.route('/admin/tecnico/<int:id>/status', methods=['PUT'])
def toggle_tecnico_status(id):
    tecnico = Tecnico.query.get_or_404(id)
    dados = request.json
    novo_status = dados.get('de_plantao')

    if novo_status is None:
        return jsonify({'erro': 'Status "de_plantao" é obrigatório.'}), 400

    tecnico.de_plantao = novo_status
    db.session.commit()
    return jsonify({'mensagem': f'Status de {tecnico.nome} atualizado para {"de plantão" if novo_status else "inativo"}.'})

# ... (restante do código do backend) ...
