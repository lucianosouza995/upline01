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

# --- FUNÇÕES AUXILIARES ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

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
            novo_chamado_aberto = Chamado(descricao_problema=dados['descricao'], pessoa_presa=bool(dados['pessoa_presa']), elevador_id=elevador.id, status='aberto')
            db.session.add(novo_chamado_aberto)
            db.session.commit()
            return jsonify({'mensagem': 'Chamado aberto! Nenhum técnico disponível, aguardando atribuição manual.', 'id_chamado': novo_chamado_aberto.id}), 201
        
        tecnico_mais_proximo = min(tecnicos_disponiveis, key=lambda t: calcular_distancia(elevador.latitude, elevador.longitude, t.last_latitude, t.last_longitude))
        novo_chamado = Chamado(descricao_problema=dados['descricao'], pessoa_presa=bool(dados['pessoa_presa']), elevador_id=elevador.id, tecnico_id=tecnico_mais_proximo.id, status='atribuido')
        db.session.add(novo_chamado)
        db.session.commit()
        return jsonify({'mensagem': 'Chamado aberto com sucesso!', 'id_chamado': novo_chamado.id, 'tecnico_atribuido': tecnico_mais_proximo.nome}), 201
    except Exception as e:
        app.logger.error(f"Erro inesperado em /chamado/abrir: {e}")
        return jsonify({'erro': 'Ocorreu um erro interno no servidor.'}), 500

@app.route('/tecnico/login', methods=['POST'])
def tecnico_login():
    dados = request.json
    tecnico = Tecnico.query.filter_by(username=dados.get('username')).first()
    if tecnico and tecnico.password == dados.get('password'):
        tecnico.de_plantao = True
        db.session.commit()
        return jsonify({'mensagem': 'Login bem-sucedido.', 'tecnico_id': tecnico.id, 'nome': tecnico.nome})
    return jsonify({'erro': 'Credenciais inválidas.'}), 401
    
@app.route('/tecnico/atualizar_localizacao', methods=['POST'])
def atualizar_localizacao():
    dados = request.json
    tecnico = Tecnico.query.get(dados.get('tecnico_id'))
    if tecnico:
        tecnico.last_latitude = dados.get('latitude')
        tecnico.last_longitude = dados.get('longitude')
        db.session.commit()
        return jsonify({'mensagem': 'Localização atualizada.'})
    return jsonify({'erro': 'Técnico não encontrado.'}), 404

@app.route('/tecnico/<int:tecnico_id>/chamados', methods=['GET'])
def get_chamados_tecnico(tecnico_id):
    chamados = Chamado.query.filter_by(tecnico_id=tecnico_id).order_by(Chamado.timestamp.desc()).all()
    return jsonify([{'id_chamado': c.id, 'endereco': c.elevador.endereco, 'descricao': c.descricao_problema, 'pessoa_presa': c.pessoa_presa, 'status': c.status, 'cliente': c.elevador.cliente.nome, 'servicos_realizados': c.servicos_realizados, 'pecas_trocadas': c.pecas_trocadas, 'observacao_texto': c.observacao_texto, 'data_finalizacao': c.data_finalizacao.strftime('%d/%m/%Y %H:%M') if c.data_finalizacao else None} for c in chamados])

@app.route('/chamado/<int:chamado_id>/finalizar', methods=['POST'])
def finalizar_chamado(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    dados = request.json
    chamado.status = 'finalizado'
    chamado.servicos_realizados = dados.get('servicos_realizados')
    chamado.pecas_trocadas = dados.get('pecas_trocadas')
    chamado.observacao_texto = dados.get('observacao_texto')
    chamado.data_finalizacao = datetime.datetime.utcnow()
    db.session.commit()
    return jsonify({'mensagem': f'Chamado #{chamado_id} finalizado com sucesso.'})

@app.route('/chamado/<int:chamado_id>/rejeitar', methods=['POST'])
def rejeitar_chamado(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    chamado.status = 'aberto'
    chamado.tecnico_id = None
    db.session.commit()
    return jsonify({'mensagem': f'Chamado #{chamado_id} rejeitado e devolvido à fila.'})

# --- ROTAS DE GESTÃO (ADMIN) ---
@app.route('/admin/clientes', methods=['GET', 'POST'])
def gerir_clientes():
    if request.method == 'GET':
        return jsonify([{'id': c.id, 'nome': c.nome, 'possui_contrato': c.possui_contrato} for c in Cliente.query.order_by(Cliente.id).all()])
    elif request.method == 'POST':
        dados = request.json
        novo_cliente = Cliente(nome=dados['nome'], possui_contrato=dados.get('possui_contrato', False))
        db.session.add(novo_cliente)
        db.session.commit()
        return jsonify({'id': novo_cliente.id, 'nome': novo_cliente.nome}), 201

@app.route('/admin/cliente/<int:id>', methods=['PUT', 'DELETE'])
def gerir_cliente_especifico(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'PUT':
        dados = request.json
        cliente.nome = dados['nome']
        cliente.possui_contrato = dados.get('possui_contrato', cliente.possui_contrato)
    elif request.method == 'DELETE':
        db.session.delete(cliente)
    db.session.commit()
    return jsonify({'mensagem': 'Operação concluída com sucesso.'})

@app.route('/admin/elevadores', methods=['GET', 'POST'])
def gerir_elevadores():
    if request.method == 'GET':
        return jsonify([{'id': e.id, 'codigo_qr': e.codigo_qr, 'endereco': e.endereco, 'latitude': e.latitude, 'longitude': e.longitude, 'cliente_id': e.cliente_id, 'cliente_nome': e.cliente.nome} for e in Elevador.query.order_by(Elevador.id).all()])
    elif request.method == 'POST':
        dados = request.json
        novo_elevador = Elevador(codigo_qr=dados['codigo_qr'], endereco=dados['endereco'], latitude=dados['latitude'], longitude=dados['longitude'], cliente_id=dados['cliente_id'])
        db.session.add(novo_elevador)
        db.session.commit()
        return jsonify({'id': novo_elevador.id, 'codigo_qr': novo_elevador.codigo_qr}), 201

@app.route('/admin/elevador/<int:id>', methods=['PUT', 'DELETE'])
def gerir_elevador_especifico(id):
    elevador = Elevador.query.get_or_404(id)
    if request.method == 'PUT':
        dados = request.json
        elevador.codigo_qr = dados['codigo_qr']
        elevador.endereco = dados['endereco']
        elevador.latitude = float(dados['latitude'])
        elevador.longitude = float(dados['longitude'])
        elevador.cliente_id = int(dados['cliente_id'])
    elif request.method == 'DELETE':
        db.session.delete(elevador)
    db.session.commit()
    return jsonify({'mensagem': 'Operação concluída com sucesso.'})

@app.route('/admin/tecnicos', methods=['GET', 'POST'])
def gerir_tecnicos():
    if request.method == 'GET':
        return jsonify([{'id': t.id, 'nome': t.nome, 'username': t.username} for t in Tecnico.query.order_by(Tecnico.id).all()])
    elif request.method == 'POST':
        dados = request.json
        novo_tecnico = Tecnico(nome=dados['nome'], username=dados['username'], password=dados['password'])
        db.session.add(novo_tecnico)
        db.session.commit()
        return jsonify({'id': novo_tecnico.id, 'nome': novo_tecnico.nome}), 201

@app.route('/admin/tecnico/<int:id>', methods=['PUT', 'DELETE'])
def gerir_tecnico_especifico(id):
    tecnico = Tecnico.query.get_or_404(id)
    if request.method == 'PUT':
        dados = request.json
        tecnico.nome = dados['nome']
        tecnico.username = dados['username']
        if dados.get('password'):
            tecnico.password = dados['password']
    elif request.method == 'DELETE':
        db.session.delete(tecnico)
    db.session.commit()
    return jsonify({'mensagem': 'Operação concluída com sucesso.'})

@app.route('/admin/chamados', methods=['GET'])
def get_todos_chamados():
    query = Chamado.query
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
        query = query.filter(Chamado.timestamp >= datetime.datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        query = query.filter(Chamado.timestamp <= datetime.datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59))

    chamados = query.order_by(Chamado.timestamp.desc()).all()
    return jsonify([{'id_chamado': c.id, 'status': c.status, 'endereco': c.elevador.endereco, 'tecnico_responsavel': c.tecnico.nome if c.tecnico else 'N/A', 'data_abertura': c.timestamp.strftime('%d/%m/%Y %H:%M')} for c in chamados])

@app.route('/admin/chamado/<int:chamado_id>/atribuir', methods=['POST'])
def atribuir_tecnico_chamado(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    dados = request.json
    tecnico_id = dados.get('tecnico_id')
    if not tecnico_id:
        return jsonify({'erro': 'ID do técnico é obrigatório.'}), 400
    
    tecnico = Tecnico.query.get_or_404(tecnico_id)
    chamado.tecnico_id = tecnico.id
    chamado.status = 'atribuido'
    db.session.commit()
    return jsonify({'mensagem': f'Chamado #{chamado.id} atribuído a {tecnico.nome}.'})

# --- LÓGICA DE INICIALIZAÇÃO DA APLICAÇÃO ---
with app.app_context():
    db.create_all()
    if not Cliente.query.first():
        print("Base de dados vazia. Populando com dados iniciais...")
        c1 = Cliente(nome='Condomínio Edifício Central', possui_contrato=True)
        c2 = Cliente(nome='Shopping Plaza Norte', possui_contrato=True)
        c3 = Cliente(nome='Torre Empresarial Faria Lima', possui_contrato=True)
        db.session.add_all([c1, c2, c3])
        e1 = Elevador(codigo_qr='ELEV-001-SP', endereco='Av. Paulista, 1000, São Paulo, SP', latitude=-23.5613, longitude=-46.6565, cliente=c1)
        e2 = Elevador(codigo_qr='ELEV-002-RJ', endereco='Av. Atlântica, 2000, Rio de Janeiro, RJ', latitude=-22.9697, longitude=-43.1868, cliente=c2)
        e3 = Elevador(codigo_qr='ELEV-003-SP', endereco='Av. Faria Lima, 4500, São Paulo, SP', latitude=-23.5869, longitude=-46.6823, cliente=c3)
        db.session.add_all([e1, e2, e3])
        t1 = Tecnico(nome='Carlos Silva', username='carlos', password='123', de_plantao=True, last_latitude=-23.55, last_longitude=-46.64)
        t2 = Tecnico(nome='Ana Souza', username='ana', password='123', de_plantao=True, last_latitude=-22.98, last_longitude=-43.20)
        t3 = Tecnico(nome='João Pereira', username='joao', password='123', de_plantao=False)
        db.session.add_all([t1, t2, t3])
        db.session.commit()
        print("Banco de dados inicializado com dados de exemplo.")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
