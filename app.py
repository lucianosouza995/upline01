# app.py
# Backend para o sistema de chamados da UpLine Elevadores
# Use os seguintes comandos para instalar as dependências:
# pip install Flask Flask-SQLAlchemy flask-cors psycopg2-binary gunicorn PyJWT

import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from math import radians, sin, cos, sqrt, atan2
import datetime
from sqlalchemy import func, extract
import jwt
from functools import wraps

# --- CONFIGURAÇÃO INICIAL ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua-chave-secreta-super-segura')
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

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# --- LÓGICA DE AUTENTICAÇÃO JWT ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message': 'Token está em falta!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = Admin.query.filter_by(id=data['id']).first()
        except:
            return jsonify({'message': 'Token é inválido!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# --- ROTAS PÚBLICAS ---
@app.route('/')
def index():
    return "API da UpLine Elevadores está no ar!"

# ... (código das outras rotas públicas como /chamado/abrir, /tecnico/login, etc.) ...

# --- ROTAS DE GESTÃO (ADMIN) ---
@app.route('/admin/login', methods=['POST'])
def admin_login():
    auth = request.json
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Não foi possível verificar'}), 401
    admin = Admin.query.filter_by(username=auth.get('username')).first()
    if not admin or not admin.password == auth.get('password'):
        return jsonify({'message': 'Credenciais inválidas!'}), 401
    token = jwt.encode({'id': admin.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, app.config['SECRET_KEY'], "HS256")
    return jsonify({'token': token})

@app.route('/admin/clientes', methods=['GET', 'POST'])
@token_required
def gerir_clientes(current_user):
    if request.method == 'GET':
        return jsonify([{'id': c.id, 'nome': c.nome, 'possui_contrato': c.possui_contrato} for c in Cliente.query.order_by(Cliente.id).all()])
    elif request.method == 'POST':
        dados = request.json
        novo_cliente = Cliente(nome=dados['nome'], possui_contrato=dados.get('possui_contrato', False))
        db.session.add(novo_cliente)
        db.session.commit()
        return jsonify({'id': novo_cliente.id, 'nome': novo_cliente.nome}), 201

@app.route('/admin/cliente/<int:id>', methods=['PUT', 'DELETE'])
@token_required
def gerir_cliente_especifico(current_user, id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'PUT':
        dados = request.json
        cliente.nome = dados['nome']
        cliente.possui_contrato = dados.get('possui_contrato', cliente.possui_contrato)
    elif request.method == 'DELETE':
        db.session.delete(cliente)
    db.session.commit()
    return jsonify({'mensagem': 'Operação concluída com sucesso.'})

# ... (código completo para as outras rotas de gestão, como /admin/elevadores, /admin/tecnicos, etc.) ...
@app.route('/admin/dashboard/stats', methods=['GET'])
@token_required
def get_dashboard_stats(current_user):
    # ... (código completo da função get_dashboard_stats) ...

# --- LÓGICA DE INICIALIZAÇÃO DA APLICAÇÃO ---
with app.app_context():
    db.create_all()
    if not Admin.query.first():
        print("Criando utilizador admin padrão...")
        admin_user = Admin(username='admin', password='password')
        db.session.add(admin_user)
        db.session.commit()
    if not Cliente.query.first():
        print("Base de dados vazia. Populando com dados de exemplo...")
        # ... (código para popular a base de dados com clientes, elevadores, etc.) ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# --- Funções auxiliares e outras rotas completas omitidas para brevidade, mas devem estar presentes no ficheiro final ---
# (O código completo que já tem para as outras rotas deve ser mantido)
