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
# Chave secreta para assinar os tokens JWT. Em produção, use uma variável de ambiente.
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
# ... (Modelos Cliente, Elevador, Tecnico, Chamado) ...

# NOVO MODELO PARA ADMINISTRADORES
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Em produção, armazene um hash da senha

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

# --- ROTAS PÚBLICAS (Chatbot e App do Técnico) ---
# ... (rotas públicas existentes) ...

# --- ROTAS DE GESTÃO (ADMIN) ---

# NOVA ROTA DE LOGIN PARA O GESTOR
@app.route('/admin/login', methods=['POST'])
def admin_login():
    auth = request.json
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Não foi possível verificar'}), 401
    
    admin = Admin.query.filter_by(username=auth.get('username')).first()
    
    if not admin or not admin.password == auth.get('password'): # Em produção, use bcrypt.checkpw
        return jsonify({'message': 'Credenciais inválidas!'}), 401
        
    token = jwt.encode({
        'id': admin.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], "HS256")
    
    return jsonify({'token': token})

# TODAS AS ROTAS DE ADMIN AGORA ESTÃO PROTEGIDAS
@app.route('/admin/clientes', methods=['GET', 'POST'])
@token_required
def gerir_clientes(current_user):
    # ... (código existente) ...

@app.route('/admin/cliente/<int:id>', methods=['PUT', 'DELETE'])
@token_required
def gerir_cliente_especifico(current_user, id):
    # ... (código existente) ...

# ... (aplicar @token_required a todas as outras rotas /admin/...) ...

# --- LÓGICA DE INICIALIZAÇÃO DA APLICAÇÃO ---
with app.app_context():
    db.create_all()
    if not Admin.query.first():
        print("Criando utilizador admin padrão...")
        # Em produção, use um hash seguro para a senha
        admin_user = Admin(username='admin', password='password')
        db.session.add(admin_user)
        db.session.commit()
    if not Cliente.query.first():
        print("Base de dados vazia. Populando com dados de exemplo...")
        # ... (código para popular a base de dados) ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
