# app.py
# Backend para o sistema de chamados da UpLine Elevadores
# Use os seguintes comandos para instalar as dependências:
# pip install Flask Flask-SQLAlchemy flask-cors

import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from math import radians, sin, cos, sqrt, atan2

# --- CONFIGURAÇÃO INICIAL ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'upline.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS (ESTRUTURA) ---
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    possui_contrato = db.Column(db.Boolean, default=True)
    elevadores = db.relationship('Elevador', backref='cliente', lazy=True)

class Elevador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_qr = db.Column(db.String(50), unique=True, nullable=False)
    endereco = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    chamados = db.relationship('Chamado', backref='elevador', lazy=True)

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
    # CORREÇÃO: A chave estrangeira estava a apontar para 'elevator.id' em vez de 'elevador.id'
    elevador_id = db.Column(db.Integer, db.ForeignKey('elevador.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnico.id'), nullable=True)

# --- FUNÇÕES AUXILIARES ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# --- ROTAS DA API (ENDPOINTS) ---
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

        # Lógica mais robusta para encontrar o técnico mais próximo
        tecnico_mais_proximo = None
        menor_distancia = float('inf')

        for tecnico in tecnicos_disponiveis:
            dist = calcular_distancia(elevador.latitude, elevador.longitude, tecnico.last_latitude, tecnico.last_longitude)
            if dist < menor_distancia:
                menor_distancia = dist
                tecnico_mais_proximo = tecnico
        
        # Verificação extra para garantir que um técnico foi encontrado
        if tecnico_mais_proximo is None:
             return jsonify({'erro': 'Não foi possível determinar o técnico mais próximo.'}), 500

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
        # Captura qualquer erro inesperado e o regista nos logs do Render
        app.logger.error(f"Erro inesperado em /chamado/abrir: {e}")
        # Retorna uma mensagem de erro genérica para o utilizador
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

@app.route('/tecnico/atualizar_localizacao', methods=['POST'])
def atualizar_localizacao():
    dados = request.json
    if not all(k in dados for k in ['tecnico_id', 'latitude', 'longitude']):
        return jsonify({'erro': 'Dados incompletos.'}), 400
    tecnico = Tecnico.query.get(dados['tecnico_id'])
    if not tecnico:
        return jsonify({'erro': 'Técnico não encontrado.'}), 404
    tecnico.last_latitude = dados['latitude']
    tecnico.last_longitude = dados['longitude']
    db.session.commit()
    return jsonify({'mensagem': 'Localização atualizada com sucesso.'})

@app.route('/tecnico/<int:tecnico_id>/chamados', methods=['GET'])
def get_chamados_tecnico(tecnico_id):
    # ALTERAÇÃO: Remove o filtro de status para buscar todos os chamados (histórico)
    # e ordena do mais novo para o mais antigo.
    chamados = Chamado.query.filter_by(tecnico_id=tecnico_id).order_by(Chamado.timestamp.desc()).all()
    lista_chamados = [{
        'id_chamado': c.id,
        'endereco': c.elevador.endereco,
        'descricao': c.descricao_problema,
        'pessoa_presa': c.pessoa_presa,
        'status': c.status,
        'cliente': c.elevador.cliente.nome
    } for c in chamados]
    return jsonify(lista_chamados)

# NOVA ROTA: Para finalizar um chamado
@app.route('/chamado/<int:chamado_id>/finalizar', methods=['POST'])
def finalizar_chamado(chamado_id):
    try:
        chamado = Chamado.query.get(chamado_id)
        if not chamado:
            return jsonify({'erro': 'Chamado não encontrado.'}), 404

        chamado.status = 'finalizado'
        db.session.commit()
        
        return jsonify({'mensagem': f'Chamado #{chamado_id} finalizado com sucesso.'})
    except Exception as e:
        app.logger.error(f"Erro ao finalizar chamado #{chamado_id}: {e}")
        return jsonify({'erro': 'Ocorreu um erro interno ao finalizar o chamado.'}), 500

# --- FUNÇÃO PARA INICIALIZAR O BANCO DE DADOS ---
def criar_dados_iniciais():
    with app.app_context():
        print("Criando um novo banco de dados com dados iniciais...")
        db.drop_all()
        db.create_all()
        # Clientes
        c1 = Cliente(nome='Condomínio Edifício Central', possui_contrato=True)
        c2 = Cliente(nome='Shopping Plaza Norte', possui_contrato=True)
        c3 = Cliente(nome='Torre Empresarial Faria Lima', possui_contrato=True)
        db.session.add_all([c1, c2, c3])
        # Elevadores
        e1 = Elevador(codigo_qr='ELEV-001-SP', endereco='Av. Paulista, 1000, São Paulo, SP', latitude=-23.5613, longitude=-46.6565, cliente=c1)
        e2 = Elevador(codigo_qr='ELEV-002-RJ', endereco='Av. Atlântica, 2000, Rio de Janeiro, RJ', latitude=-22.9697, longitude=-43.1868, cliente=c2)
        e3 = Elevador(codigo_qr='ELEV-002-SP', endereco='Av. Faria Lima, 4500, São Paulo, SP', latitude=-23.5869, longitude=-46.6823, cliente=c3)
        db.session.add_all([e1, e2, e3])
        # Técnicos
        t1 = Tecnico(nome='Carlos Silva', username='carlos', password='123', de_plantao=True, last_latitude=-23.55, last_longitude=-46.64)
        t2 = Tecnico(nome='Ana Souza', username='ana', password='123', de_plantao=True, last_latitude=-22.98, last_longitude=-43.20)
        t3 = Tecnico(nome='João Pereira', username='joao', password='123', de_plantao=False)
        db.session.add_all([t1, t2, t3])
        db.session.commit()
        print("Banco de dados inicializado com dados de exemplo.")

# --- LÓGICA DE INICIALIZAÇÃO DA APLICAÇÃO ---
# Esta parte do código será executada quando o Gunicorn importar o 'app.py' no Render.
# Ele verifica se o ficheiro da base de dados existe e, se não, cria-o.
with app.app_context():
    db.create_all()
    # Verifica se a base de dados está vazia para adicionar os dados iniciais.
    if not Tecnico.query.first():
        print("Base de dados vazia. Populando com dados iniciais...")
        # Clientes
        c1 = Cliente(nome='Condomínio Edifício Central', possui_contrato=True)
        c2 = Cliente(nome='Shopping Plaza Norte', possui_contrato=True)
        c3 = Cliente(nome='Torre Empresarial Faria Lima', possui_contrato=True)
        db.session.add_all([c1, c2, c3])
        # Elevadores
        e1 = Elevador(codigo_qr='ELEV-001-SP', endereco='Av. Paulista, 1000, São Paulo, SP', latitude=-23.5613, longitude=-46.6565, cliente=c1)
        e2 = Elevador(codigo_qr='ELEV-002-RJ', endereco='Av. Atlântica, 2000, Rio de Janeiro, RJ', latitude=-22.9697, longitude=-43.1868, cliente=c2)
        e3 = Elevador(codigo_qr='ELEV-002-SP', endereco='Av. Faria Lima, 4500, São Paulo, SP', latitude=-23.5869, longitude=-46.6823, cliente=c3)
        db.session.add_all([e1, e2, e3])
        # Técnicos
        t1 = Tecnico(nome='Carlos Silva', username='carlos', password='123', de_plantao=True, last_latitude=-23.55, last_longitude=-46.64)
        t2 = Tecnico(nome='Ana Souza', username='ana', password='123', de_plantao=True, last_latitude=-22.98, last_longitude=-43.20)
        t3 = Tecnico(nome='João Pereira', username='joao', password='123', de_plantao=False)
        db.session.add_all([t1, t2, t3])
        db.session.commit()
        print("Banco de dados inicializado com dados de exemplo.")


if __name__ == '__main__':
    # Para desenvolvimento local, a lógica acima também garante que a BD está pronta.
    app.run(debug=True, host='0.0.0.0')
