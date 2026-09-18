# Encantar Cerimonial

Web service Flask profissional para o site institucional do **Encantar Cerimonial**, com site público, painel administrativo, banco de dados, uploads, depoimentos, eventos, serviços, equipe, galeria, configurações e backup local.

## Estrutura

- Site público: Início, Sobre Nós, Equipe, Serviços, Eventos, Galeria, Depoimentos, FAQ, Contato e Orçamento.
- Admin: Dashboard, Eventos, Galeria, Feedbacks, Serviços, Equipe, Imagens e Configurações.
- Mídia: fotos e organização básica por categoria.
- Contato: WhatsApp, Instagram, E-mail, Facebook e Google Maps.
- Sistema: login, hash de senha, sessão, proteção CSRF, SQLite/PostgreSQL, uploads, páginas de erro e backup local SQLite.

## Rodar no computador

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Acesse `http://localhost:5000`.

### Login inicial

Por padrão:
- E-mail: `admin@encantarcerimonial.com`
- Senha: `Encantar@123`

**Troque a senha antes de colocar o projeto em produção.**

Você também pode definir:
- `SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `DATABASE_URL`

## GitHub

Crie um repositório, envie todos os arquivos e faça o primeiro commit.

Não envie dados sensíveis nem arquivos de banco pessoal. O `.gitignore` já protege a pasta `instance/`, uploads e backups.

## Render

1. Crie um Web Service no Render.
2. Conecte o repositório do GitHub.
3. Build Command:
   `pip install -r requirements.txt`
4. Start Command:
   `gunicorn app:app`
5. Defina as variáveis de ambiente:
   - `SECRET_KEY` = uma chave aleatória longa
   - `ADMIN_EMAIL` = seu e-mail de administrador
   - `ADMIN_PASSWORD` = uma senha forte
   - `DATABASE_URL` = opcional; para produção persistente, prefira PostgreSQL.

### Observação importante sobre uploads no Render

O armazenamento local de arquivos pode ser efêmero dependendo da infraestrutura/plano. Para fotos permanentes em produção, use um serviço de armazenamento persistente (por exemplo, um bucket S3 compatível) ou disco persistente do provedor. A aplicação já separa os uploads em `static/uploads` para facilitar essa evolução.

## Onde configurar WhatsApp e redes sociais

Depois de entrar em `/admin`, abra **Configurações** e preencha WhatsApp, Instagram, Facebook, e-mail, endereço, Google Maps e demais dados. Não é necessário editar o código.

## Segurança

- Senhas armazenadas com hash.
- Sessão administrativa.
- Proteção CSRF nos formulários.
- Upload limitado a imagens.
- `SECRET_KEY` configurável por variável de ambiente.

## Próximas integrações

O projeto foi estruturado para receber futuramente Cloudinary/S3, PostgreSQL, e-mail transacional, analytics e editor de conteúdo mais avançado sem precisar refazer o site público.
