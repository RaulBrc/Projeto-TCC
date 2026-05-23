from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configura o banco de dados SQLite (vai gerar um arquivo chamado trituno.db na raiz)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trituno.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# =========================================
# MODELO DO BANCO DE DADOS (Tabela de Usuário)
# =========================================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    progresso = db.Column(db.Integer, default=25) # Começa em 25% para teste visual
    cristais = db.Column(db.Integer, default=350)
    vidas = db.Column(db.Integer, default=5)
    ofensiva = db.Column(db.Integer, default=7)

# =========================================
# ROTAS DO SITE (Apontando para os seus HTMLs)
# =========================================

@app.route('/')
def pagina_home():
    # Renderiza o index.html que está solto dentro de templates
    return render_template('index.html')

@app.route('/licoes')
def pagina_licoes():
    # Cria o usuário padrão no banco se ele ainda não existir
    usuario = Usuario.query.first()
    if not usuario:
        usuario = Usuario(nome="Músico Aprendiz")
        db.session.add(usuario)
        db.session.commit()
    
    # Renderiza o licoes.html de dentro da pasta meu-projeto
    return render_template('meu-projeto/licoes.html', usuario=usuario)

@app.route('/loja')
def pagina_loja():
    usuario = Usuario.query.first()
    return render_template('meu-projeto/loja.html', usuario=usuario)

@app.route('/ranking')
def pagina_ranking():
    usuario = Usuario.query.first()
    return render_template('meu-projeto/ranking.html', usuario=usuario)

@app.route('/configuracoes')
def pagina_configuracoes():
    usuario = Usuario.query.first()
    return render_template('meu-projeto/configuracoes.html', usuario=usuario)

@app.route('/registro')
def pagina_registro():
    # Abre o Registro.html de dentro de meu-projeto
    return render_template('meu-projeto/Registro.html')

@app.route('/login')
def pagina_login():
    # Abre o login.html de dentro de meu-projeto
    return render_template('meu-projeto/login.html')

@app.route('/exercicio1')
def pagina_exercicio1():
    # Abre o exercicio1.html de dentro de meu-projeto
    return render_template('modulo1/exercicio1.html')

@app.route('/introducao')
def pagina_introducao():
    # Abre o introducao.html de dentro de meu-projeto
    return render_template('modulo1/introducao.html')

# Inicializa o banco de dados e roda o servidor
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Cria o arquivo do banco automaticamente
    app.run(debug=True)