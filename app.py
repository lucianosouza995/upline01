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
# --- CORREÇÃO DE CORS ---
# Configuração mais explícita para garantir que os pedidos preflight (OPTIONS) sejam aceites.
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
@app.route('/')
def index():
    return "API da UpLine Elevadores está no ar!"

@app.route('/chamado/abrir', methods=['POST'])
def abrir_chamado():
    dados = request.json
    if not all(k in dados for k in ['codigo_qr', 'pessoa_presa', 'descricao']):
        return jsonify({'erro': 'Dados incompletos fornecidos.'}), 400

    try:
        elevador = Elevador.query.filter_by(codigo_qr=dados['codigo_qr']).first()
        if not elevador:
            return jsonify({'erro': f"O elevador com o código '{dados['codigo_qr']}' não foi encontrado."}), 404

        tecnicos_disponiveis = Tecnico.query.filter_by(de_plantao=True).filter(Tecnico.last_latitude.isnot(None)).all()
        if not tecnicos_disponiveis:
            return jsonify({'erro': 'Nenhum técnico disponível no momento.'}), 503

        tecnico_mais_proximo = min(tecnicos_disponiveis, key=lambda t: calcular_distancia(elevador.latitude, elevador.longitude, t.last_latitude, t.last_longitude))
        menor_distancia = calcular_distancia(elevador.latitude, elevador.longitude, tecnico_mais_proximo.last_latitude, tecnico_mais_proximo.last_longitude)
        
        novo_chamado = Chamado(
            descricao_problema=dados['descricao'],
            pessoa_presa=bool(dados['pessoa_presa']),
            elevador_id=elevador.id,
            tecnico_id=tecnico_mais_proximo.id,
            status='atribuido'
        )
        db.session.add(novo_chamado)
        db.session.commit()

        return jsonify({
            'mensagem': 'Chamado aberto com sucesso!',
            'id_chamado': novo_chamado.id,
            'tecnico_atribuido': tecnico_mais_proximo.nome,
            'distancia_km': round(menor_distancia, 2)
        }), 201

    except Exception as e:
        app.logger.error(f"Erro inesperado em /chamado/abrir: {e}")
        return jsonify({'erro': 'Ocorreu um erro interno no servidor. A equipa foi notificada.'}), 500

@app.route('/tecnico/login', methods=['POST'])
def tecnico_login():
    dados = request.json
    tecnico = Tecnico.query.filter_by(username=dados.get('username')).first()
    if tecnico and tecnico.password == dados.get('password'):
        tecnico.de_plantao = True
        db.session.commit()
        return jsonify({'mensagem': 'Login bem-sucedido.', 'tecnico_id': tecnico.id, 'nome': tecnico.nome})
    return jsonify({'erro': 'Credenciais inválidas.'}), 401
    
# ... (restante do código do backend) ...
