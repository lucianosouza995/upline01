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
CORS(app)

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
# ... (código existente) ...

@app.route('/tecnico/login', methods=['POST'])
# ... (código existente) ...

@app.route('/tecnico/<int:tecnico_id>/chamados', methods=['GET'])
# ... (código existente) ...

@app.route('/chamado/<int:chamado_id>/finalizar', methods=['POST'])
# ... (código existente) ...

# --- NOVAS ROTAS DE GESTÃO (ADMIN) ---

# --- GESTÃO DE CLIENTES ---
@app.route('/admin/clientes', methods=['GET', 'POST'])
def gerir_clientes():
    if request.method == 'GET':
        clientes = Cliente.query.all()
        return jsonify([{'id': c.id, 'nome': c.nome, 'possui_contrato': c.possui_contrato} for c in clientes])
    elif request.method == 'POST':
        dados = request.json
        novo_cliente = Cliente(nome=dados['nome'], possui_contrato=dados['possui_contrato'])
        db.session.add(novo_cliente)
        db.session.commit()
        return jsonify({'id': novo_cliente.id, 'nome': novo_cliente.nome}), 201

@app.route('/admin/cliente/<int:id>', methods=['PUT', 'DELETE'])
def gerir_cliente_especifico(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'PUT':
        dados = request.json
        cliente.nome = dados['nome']
        cliente.possui_contrato = dados['possui_contrato']
        db.session.commit()
        return jsonify({'mensagem': 'Cliente atualizado com sucesso.'})
    elif request.method == 'DELETE':
        db.session.delete(cliente)
        db.session.commit()
        return jsonify({'mensagem': 'Cliente removido com sucesso.'})

# --- GESTÃO DE ELEVADORES ---
@app.route('/admin/elevadores', methods=['GET', 'POST'])
def gerir_elevadores():
    if request.method == 'GET':
        elevadores = Elevador.query.all()
        return jsonify([{
            'id': e.id, 'codigo_qr': e.codigo_qr, 'endereco': e.endereco, 
            'latitude': e.latitude, 'longitude': e.longitude, 'cliente_id': e.cliente_id,
            'cliente_nome': e.cliente.nome
        } for e in elevadores])
    elif request.method == 'POST':
        dados = request.json
        novo_elevador = Elevador(
            codigo_qr=dados['codigo_qr'], endereco=dados['endereco'],
            latitude=dados['latitude'], longitude=dados['longitude'],
            cliente_id=dados['cliente_id']
        )
        db.session.add(novo_elevador)
        db.session.commit()
        return jsonify({'id': novo_elevador.id, 'codigo_qr': novo_elevador.codigo_qr}), 201

# --- GESTÃO DE TÉCNICOS ---
@app.route('/admin/tecnicos', methods=['GET', 'POST'])
def gerir_tecnicos():
    if request.method == 'GET':
        tecnicos = Tecnico.query.all()
        return jsonify([{'id': t.id, 'nome': t.nome, 'username': t.username} for t in tecnicos])
    elif request.method == 'POST':
        dados = request.json
        # NOTA: Em produção, a senha deve ser "hasheada"
        novo_tecnico = Tecnico(nome=dados['nome'], username=dados['username'], password=dados['password'])
        db.session.add(novo_tecnico)
        db.session.commit()
        return jsonify({'id': novo_tecnico.id, 'nome': novo_tecnico.nome}), 201

# --- VISUALIZAÇÃO DE CHAMADOS ---
@app.route('/admin/chamados', methods=['GET'])
def get_todos_chamados():
    chamados = Chamado.query.order_by(Chamado.timestamp.desc()).all()
    lista_chamados = [{
        'id_chamado': c.id,
        'status': c.status,
        'endereco': c.elevador.endereco,
        'tecnico_responsavel': c.tecnico.nome if c.tecnico else 'N/A',
        'data_abertura': c.timestamp.strftime('%d/%m/%Y %H:%M'),
        'data_finalizacao': c.data_finalizacao.strftime('%d/%m/%Y %H:%M') if c.data_finalizacao else None
    } for c in chamados]
    return jsonify(lista_chamados)

# --- LÓGICA DE INICIALIZAÇÃO DA APLICAÇÃO ---
with app.app_context():
    db.create_all()
    if not Cliente.query.first():
        print("Base de dados vazia. Populando com dados iniciais...")
        # ... (código para popular a base de dados) ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
