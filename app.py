# app.py
# Backend para o sistema de chamados da UpLine Elevadores
# Use os seguintes comandos para instalar as dependências:
# pip install Flask Flask-SQLAlchemy flask-cors

import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS # Importar o CORS
from math import radians, sin, cos, sqrt, atan2

# --- CONFIGURAÇÃO INICIAL ---
# Define o caminho base do projeto
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
CORS(app) # Habilitar o CORS para toda a aplicação

# Configuração do banco de dados SQLite
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
    # ID único usado no QR Code, ex: "ELEV-001-SP"
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
    # Em um app real, a senha deve ser "hasheada" (ex: com werkzeug.security)
    password = db.Column(db.String(100), nullable=False) 
    de_plantao = db.Column(db.Boolean, default=False)
    # Última localização conhecida do técnico
    last_latitude = db.Column(db.Float, nullable=True)
    last_longitude = db.Column(db.Float, nullable=True)
    chamados = db.relationship('Chamado', backref='tecnico', lazy=True)

class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    descricao_problema = db.Column(db.String(500), nullable=False)
    pessoa_presa = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='aberto') # aberto, atribuido, em_andamento, finalizado
    elevador_id = db.Column(db.Integer, db.ForeignKey('elevador.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnico.id'), nullable=True) # Pode ser nulo inicialmente

# --- FUNÇÕES AUXILIARES ---

def calcular_distancia(lat1, lon1, lat2, lon2):
    """Calcula a distância em km entre dois pontos de GPS (fórmula de Haversine)."""
    R = 6371.0  # Raio da Terra em km

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distancia = R * c
    return distancia

# --- ROTAS DA API (ENDPOINTS) ---

@app.route('/')
def index():
    return "API da UpLine Elevadores está no ar!"

@app.route('/chamado/abrir', methods=['POST'])
def abrir_chamado():
    """Endpoint principal para o chatbot abrir um novo chamado."""
    dados = request.json
    
    # Validação dos dados recebidos
    if not all(k in dados for k in ['codigo_qr', 'pessoa_presa', 'descricao']):
        return jsonify({'erro': 'Dados incompletos fornecidos.'}), 400

    # 1. Encontrar o elevador pelo código do QR Code
    elevador = Elevador.query.filter_by(codigo_qr=dados['codigo_qr']).first()
    if not elevador:
        return jsonify({'erro': 'Elevador não encontrado.'}), 404

    # 2. Encontrar todos os técnicos de plantão que têm localização registrada
    tecnicos_disponiveis = Tecnico.query.filter_by(de_plantao=True).filter(Tecnico.last_latitude.isnot(None)).all()
    if not tecnicos_disponiveis:
        return jsonify({'erro': 'Nenhum técnico disponível no momento.'}), 503

    # 3. Calcular o técnico mais próximo
    tecnico_mais_proximo = None
    menor_distancia = float('inf')

    for tecnico in tecnicos_disponiveis:
        dist = calcular_distancia(elevador.latitude, elevador.longitude, tecnico.last_latitude, tecnico.last_longitude)
        if dist < menor_distancia:
            menor_distancia = dist
            tecnico_mais_proximo = tecnico

    # 4. Criar e salvar o novo chamado no banco de dados
    novo_chamado = Chamado(
        descricao_problema=dados['descricao'],
        pessoa_presa=bool(dados['pessoa_presa']),
        elevador_id=elevador.id,
        tecnico_id=tecnico_mais_proximo.id if tecnico_mais_proximo else None,
        status='atribuido' if tecnico_mais_proximo else 'aberto'
    )
    
    db.session.add(novo_chamado)
    db.session.commit()

    return jsonify({
        'mensagem': 'Chamado aberto com sucesso!',
        'id_chamado': novo_chamado.id,
        'tecnico_atribuido': tecnico_mais_proximo.nome if tecnico_mais_proximo else 'Aguardando atribuição',
        'distancia_km': round(menor_distancia, 2) if tecnico_mais_proximo else -1
    }), 201


@app.route('/tecnico/login', methods=['POST'])
def tecnico_login():
    """Endpoint para o técnico fazer login."""
    dados = request.json
    tecnico = Tecnico.query.filter_by(username=dados.get('username')).first()
    
    # Lembrete: em produção, compare o hash da senha, não a senha em texto plano!
    if tecnico and tecnico.password == dados.get('password'):
        tecnico.de_plantao = True
        db.session.commit()
        return jsonify({'mensagem': 'Login bem-sucedido.', 'tecnico_id': tecnico.id})
    
    return jsonify({'erro': 'Credenciais inválidas.'}), 401

@app.route('/tecnico/logout', methods=['POST'])
def tecnico_logout():
    """Endpoint para o técnico fazer logout."""
    dados = request.json
    tecnico = Tecnico.query.filter_by(id=dados.get('tecnico_id')).first()
    if tecnico:
        tecnico.de_plantao = False
        db.session.commit()
        return jsonify({'mensagem': 'Logout realizado com sucesso.'})
    return jsonify({'erro': 'Técnico não encontrado.'}), 404


@app.route('/tecnico/atualizar_localizacao', methods=['POST'])
def atualizar_localizacao():
    """Endpoint para o app do técnico enviar a localização GPS."""
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
    """Endpoint para o técnico ver seus chamados."""
    tecnico = Tecnico.query.get(tecnico_id)
    if not tecnico:
        return jsonify({'erro': 'Técnico não encontrado.'}), 404
        
    chamados = Chamado.query.filter_by(tecnico_id=tecnico.id).filter(Chamado.status != 'finalizado').all()
    
    lista_chamados = []
    for chamado in chamados:
        lista_chamados.append({
            'id_chamado': chamado.id,
            'endereco': chamado.elevador.endereco,
            'descricao': chamado.descricao_problema,
            'pessoa_presa': chamado.pessoa_presa,
            'status': chamado.status,
            'cliente': chamado.elevador.cliente.nome
        })
        
    return jsonify(lista_chamados)


# --- FUNÇÃO PARA INICIALIZAR O BANCO DE DADOS COM DADOS DE EXEMPLO ---
def criar_dados_iniciais():
    with app.app_context():
        db.drop_all() # Apaga tudo para um começo limpo
        db.create_all()

        # Clientes
        cliente1 = Cliente(nome='Condomínio Edifício Central', possui_contrato=True)
        cliente2 = Cliente(nome='Shopping Plaza Norte', possui_contrato=True)
        db.session.add_all([cliente1, cliente2])
        db.session.commit()

        # Elevadores
        elevador1 = Elevador(codigo_qr='ELEV-001-SP', endereco='Av. Paulista, 1000, São Paulo, SP', latitude=-23.5613, longitude=-46.6565, cliente_id=cliente1.id)
        elevador2 = Elevador(codigo_qr='ELEV-002-RJ', endereco='Av. Atlântica, 2000, Rio de Janeiro, RJ', latitude=-22.9697, longitude=-43.1868, cliente_id=cliente2.id)
        db.session.add_all([elevador1, elevador2])
        db.session.commit()
        
        # Técnicos
        tecnico1 = Tecnico(nome='Carlos Silva', username='carlos', password='123', de_plantao=True, last_latitude=-23.55, last_longitude=-46.64) # Perto da Paulista
        tecnico2 = Tecnico(nome='Ana Souza', username='ana', password='123', de_plantao=True, last_latitude=-22.98, last_longitude=-43.20) # Perto de Copacabana
        tecnico3 = Tecnico(nome='João Pereira', username='joao', password='123', de_plantao=False) # Fora de serviço
        db.session.add_all([tecnico1, tecnico2, tecnico3])
        db.session.commit()
        
        print("Banco de dados inicializado com dados de exemplo.")


if __name__ == '__main__':
    # Cria o banco de dados e os dados iniciais se o arquivo 'upline.db' não existir
    if not os.path.exists(os.path.join(basedir, 'upline.db')):
        criar_dados_iniciais()
    # Inicia o servidor Flask
    app.run(debug=True, host='0.0.0.0')

