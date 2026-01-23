# -*- coding: utf-8 -*-
"""
Assistente de Configuração - Quintessa Editais

Este script ajuda a configurar a autenticação do Google Sheets de duas formas:
1. Service Account (RECOMENDADO) - Para distribuição
2. OAuth Pessoal (LEGADO) - Para desenvolvimento

Requisitos:
  pip install google-auth google-auth-oauthlib google-api-python-client python-dotenv gspread
"""

import os
import sys
import json
import webbrowser
from pathlib import Path
from typing import Optional
from datetime import datetime

# Tenta importar dependências opcionais
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    import gspread
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

# Configurações
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

ROOT_DIR = Path(__file__).resolve().parent


# =============================================================================
# UTILIDADES
# =============================================================================

def clear_screen():
    """Limpa a tela do terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Imprime um cabeçalho formatado."""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}".center(width))
    print("=" * width)


def print_step(step: int, total: int, description: str):
    """Imprime o passo atual."""
    print(f"\n[Passo {step}/{total}] {description}")
    print("-" * 50)


def ask(prompt: str, default: Optional[str] = None, required: bool = True) -> str:
    """Faz uma pergunta ao usuário."""
    suffix = f" [{default}]" if default else ""
    suffix += ": " if required else " (opcional): "
    
    while True:
        value = input(f"{prompt}{suffix}").strip()
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        print("  ⚠️  Este campo é obrigatório. Tente novamente.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Faz uma pergunta sim/não."""
    suffix = " [S/n]" if default else " [s/N]"
    while True:
        value = input(f"{prompt}{suffix}: ").strip().lower()
        if value in ("", "s", "sim", "y", "yes"):
            return True if (value or default) else False
        if value in ("n", "nao", "não", "no"):
            return False
        print("  Por favor, responda 's' para sim ou 'n' para não.")


def pause():
    """Pausa para o usuário ler."""
    input("\nPressione ENTER para continuar...")


# =============================================================================
# VALIDAÇÃO DE SERVICE ACCOUNT
# =============================================================================

def validate_service_account(path: Path) -> tuple[bool, str, Optional[dict]]:
    """
    Valida um arquivo de Service Account.
    Retorna: (válido, mensagem, dados)
    """
    if not path.exists():
        return False, f"Arquivo não encontrado: {path}", None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"JSON inválido: {e}", None
    
    # Verifica campos obrigatórios
    required_fields = ['type', 'client_email', 'private_key', 'project_id']
    missing = [f for f in required_fields if f not in data]
    
    if missing:
        return False, f"Campos faltando: {', '.join(missing)}", None
    
    if data.get('type') != 'service_account':
        return False, f"Tipo inválido: {data.get('type')} (esperado: service_account)", None
    
    return True, "Arquivo válido!", data


def test_service_account_connection(sa_path: Path, sheet_url: str) -> tuple[bool, str]:
    """
    Testa a conexão com a planilha usando o Service Account.
    """
    if not GOOGLE_LIBS_AVAILABLE:
        return False, "Bibliotecas Google não instaladas."
    
    try:
        creds = ServiceAccountCredentials.from_service_account_file(
            str(sa_path),
            scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(sheet_url)
        return True, f"Conexão OK! Planilha: '{sh.title}'"
    except gspread.exceptions.SpreadsheetNotFound:
        return False, (
            "Planilha não encontrada ou sem permissão.\n"
            "Certifique-se de compartilhar a planilha com o email do Service Account."
        )
    except Exception as e:
        return False, f"Erro de conexão: {e}"


# =============================================================================
# SETUP SERVICE ACCOUNT (RECOMENDADO)
# =============================================================================

def setup_service_account():
    """Configura autenticação via Service Account."""
    clear_screen()
    print_header("CONFIGURAÇÃO - SERVICE ACCOUNT")
    
    print("""
Este é o método RECOMENDADO para distribuição.

Vantagens:
  ✓ Não expira
  ✓ Fácil de distribuir (só 1 arquivo)
  ✓ Mais seguro
  ✓ Profissional
    """)
    
    total_steps = 5
    
    # Passo 1: Verificar se já existe
    print_step(1, total_steps, "Verificando arquivos existentes")
    
    existing_sa = ROOT_DIR / "service_account.json"
    if existing_sa.exists():
        valid, msg, data = validate_service_account(existing_sa)
        if valid:
            print(f"  ✓ Arquivo encontrado: {existing_sa}")
            print(f"  ✓ Email: {data['client_email']}")
            if not ask_yes_no("Deseja substituir o arquivo existente?", default=False):
                return configure_env_file(existing_sa)
    
    # Passo 2: Instruções para criar no Google Cloud
    print_step(2, total_steps, "Criar Service Account no Google Cloud Console")
    
    print("""
Siga estas etapas no Google Cloud Console:

1. Acesse: https://console.cloud.google.com/
2. Selecione ou crie um projeto
3. Vá em: APIs & Services → Credentials
4. Clique: "Create Credentials" → "Service Account"
5. Dê um nome (ex: quintessa-sheets-bot)
6. Clique "Create and Continue" → "Done"
7. Clique na Service Account criada
8. Aba "Keys" → "Add Key" → "Create new key" → "JSON"
9. Salve o arquivo como: service_account.json
""")
    
    if ask_yes_no("Abrir o Google Cloud Console no navegador?"):
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
        print("\n  🌐 Navegador aberto! Complete os passos acima.")
    
    pause()
    
    # Passo 3: Localizar o arquivo
    print_step(3, total_steps, "Localizar arquivo de Service Account")
    
    print(f"  Coloque o arquivo 'service_account.json' em:")
    print(f"  📁 {ROOT_DIR}")
    
    while True:
        pause()
        
        # Procura o arquivo
        sa_path = ROOT_DIR / "service_account.json"
        if not sa_path.exists():
            # Tenta encontrar qualquer JSON com 'service_account' no conteúdo
            for f in ROOT_DIR.glob("*.json"):
                valid, _, _ = validate_service_account(f)
                if valid:
                    sa_path = f
                    break
        
        if sa_path.exists():
            valid, msg, data = validate_service_account(sa_path)
            if valid:
                print(f"\n  ✓ Arquivo encontrado e validado!")
                print(f"  ✓ Projeto: {data['project_id']}")
                print(f"  ✓ Email: {data['client_email']}")
                break
            else:
                print(f"\n  ❌ {msg}")
                if not ask_yes_no("Tentar novamente?"):
                    return False
        else:
            print(f"\n  ❌ Arquivo não encontrado em: {ROOT_DIR}")
            if not ask_yes_no("Tentar novamente?"):
                return False
    
    # Renomeia se necessário
    if sa_path.name != "service_account.json":
        new_path = ROOT_DIR / "service_account.json"
        sa_path.rename(new_path)
        sa_path = new_path
        print(f"  ✓ Arquivo renomeado para: service_account.json")
    
    # Passo 4: Compartilhar planilha
    print_step(4, total_steps, "Compartilhar planilha com o Service Account")
    
    service_email = data['client_email']
    print(f"""
IMPORTANTE: Você precisa compartilhar sua planilha Google com:

📧 {service_email}

Passos:
1. Abra sua planilha no Google Sheets
2. Clique em "Compartilhar" (canto superior direito)
3. Cole o email acima
4. Dê permissão de "Editor"
5. Clique em "Enviar"
""")
    
    # Copia o email para a área de transferência se possível
    try:
        import subprocess
        subprocess.run(['clip'], input=service_email.encode(), check=True)
        print(f"  📋 Email copiado para a área de transferência!")
    except:
        pass
    
    pause()
    
    # Passo 5: Configurar .env
    print_step(5, total_steps, "Configurar arquivo .env")
    return configure_env_file(sa_path)


def configure_env_file(sa_path: Path) -> bool:
    """Configura o arquivo .env com SHEET_URL e testa a conexão."""
    
    env_path = ROOT_DIR / ".env"
    existing_vars = {}
    
    # Lê variáveis existentes
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    existing_vars[key.strip()] = value.strip().strip('"')
    
    # Pede SHEET_URL
    current_sheet = existing_vars.get("SHEET_URL", "")
    if current_sheet:
        print(f"  URL atual: {current_sheet[:60]}...")
    
    sheet_url = ask(
        "Cole a URL da planilha Google Sheets",
        default=current_sheet if current_sheet else None
    )
    
    # Pede PERPLEXITY_API_KEY (opcional)
    current_pplx = existing_vars.get("PERPLEXITY_API_KEY", "")
    pplx_key = ask(
        "Perplexity API Key",
        default=current_pplx if current_pplx else None,
        required=False
    )
    
    # Testa conexão
    print("\n  🔄 Testando conexão com a planilha...")
    success, msg = test_service_account_connection(sa_path, sheet_url)
    
    if success:
        print(f"  ✓ {msg}")
    else:
        print(f"  ❌ {msg}")
        if not ask_yes_no("Deseja salvar mesmo assim?", default=False):
            return False
    
    # Salva .env
    if env_path.exists():
        backup = ROOT_DIR / f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        env_path.rename(backup)
        print(f"  📦 Backup criado: {backup.name}")
    
    lines = [
        "# Quintessa Editais - Configuração",
        f"# Gerado em: {datetime.now().isoformat()}",
        "",
        "# URL da planilha Google Sheets",
        f'SHEET_URL="{sheet_url}"',
        "",
    ]
    
    if pplx_key:
        lines.extend([
            "# Perplexity API (para análise de editais)",
            f'PERPLEXITY_API_KEY="{pplx_key}"',
            "",
        ])
    
    env_path.write_text("\n".join(lines), encoding='utf-8')
    
    print(f"\n  ✓ Arquivo .env salvo em: {env_path}")
    
    # Resumo final
    print_header("CONFIGURAÇÃO CONCLUÍDA!")
    print(f"""
Arquivos configurados:
  ✓ {sa_path.name}
  ✓ .env

Para distribuir o executável, envie:
  📁 api.exe (ou o nome do seu executável)
  📁 config.json
  📁 service_account.json
  📁 .env

O usuário final só precisa extrair e executar!
""")
    
    pause()
    return True


# =============================================================================
# SETUP OAUTH PESSOAL (LEGADO)
# =============================================================================

def setup_oauth_legacy():
    """Configura autenticação via OAuth pessoal (método legado)."""
    clear_screen()
    print_header("CONFIGURAÇÃO - OAUTH PESSOAL (LEGADO)")
    
    print("""
⚠️  Este método é LEGADO e não recomendado para distribuição.
    Use apenas para desenvolvimento local.

    Para distribuição, use Service Account.
""")
    
    if not ask_yes_no("Deseja continuar mesmo assim?", default=False):
        return False
    
    if not GOOGLE_LIBS_AVAILABLE:
        print("\n❌ Bibliotecas Google não instaladas.")
        print("   Execute: pip install google-auth google-auth-oauthlib")
        pause()
        return False
    
    # Verifica client_secret.json
    client_json = ROOT_DIR / "client_secret.json"
    if not client_json.exists():
        print(f"""
❌ Arquivo client_secret.json não encontrado.

Para criar:
1. Acesse: https://console.cloud.google.com/apis/credentials
2. Crie um "OAuth 2.0 Client ID" do tipo "Desktop app"
3. Baixe o JSON e salve como: {client_json}
""")
        pause()
        return False
    
    # Pede dados
    print("\n== Dados para o .env ==")
    sheet_url = ask("Cole a URL da sua planilha Google (SHEET_URL)")
    pplx_key = ask("Perplexity API key", required=False)
    
    # Fluxo OAuth
    print("\n🌐 Abrindo navegador para autorização...")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_json), SCOPES)
        creds = flow.run_local_server(
            host="localhost",
            port=8080,
            prompt="consent",
            access_type="offline",
        )
        
        if not creds.valid:
            creds.refresh(Request())
        
        refresh_token = creds.refresh_token
        if not refresh_token:
            print("\n❌ Não recebi refresh_token.")
            print("   Revogue acessos em https://myaccount.google.com/permissions")
            pause()
            return False
        
    except Exception as e:
        print(f"\n❌ Erro no fluxo OAuth: {e}")
        pause()
        return False
    
    # Lê client_id/client_secret
    cfg = json.loads(client_json.read_text(encoding='utf-8'))
    client_info = cfg["installed"]
    
    # Salva .env
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        backup = ROOT_DIR / ".env.backup"
        env_path.rename(backup)
        print(f"⚠️  Backup criado: {backup}")
    
    lines = [
        "# Quintessa Editais - OAuth Pessoal (LEGADO)",
        f"# Gerado em: {datetime.now().isoformat()}",
        "",
        f'SHEET_URL="{sheet_url}"',
        f'GOOGLE_CLIENT_ID="{client_info["client_id"]}"',
        f'GOOGLE_CLIENT_SECRET="{client_info["client_secret"]}"',
        f'GOOGLE_REFRESH_TOKEN="{refresh_token}"',
        f'GOOGLE_TOKEN_URI="{client_info.get("token_uri", "https://oauth2.googleapis.com/token")}"',
    ]
    
    if pplx_key:
        lines.append(f'PERPLEXITY_API_KEY="{pplx_key}"')
    
    env_path.write_text("\n".join(lines) + "\n", encoding='utf-8')
    
    # Salva token.json também
    (ROOT_DIR / "token.json").write_text(creds.to_json(), encoding='utf-8')
    
    print(f"\n✓ .env salvo em: {env_path}")
    print(f"✓ token.json salvo em: {ROOT_DIR / 'token.json'}")
    
    pause()
    return True


# =============================================================================
# DIAGNÓSTICO
# =============================================================================

def run_diagnostics():
    """Executa diagnóstico completo da configuração."""
    clear_screen()
    print_header("DIAGNÓSTICO DE CONFIGURAÇÃO")
    
    print("\n📁 Diretório:", ROOT_DIR)
    print("-" * 50)
    
    # Service Account
    sa_path = ROOT_DIR / "service_account.json"
    print("\n🔑 Service Account:")
    if sa_path.exists():
        valid, msg, data = validate_service_account(sa_path)
        if valid:
            print(f"   ✓ Arquivo: {sa_path.name}")
            print(f"   ✓ Projeto: {data['project_id']}")
            print(f"   ✓ Email: {data['client_email']}")
        else:
            print(f"   ⚠️  Arquivo existe mas inválido: {msg}")
    else:
        print(f"   ✗ Não encontrado")
    
    # .env
    env_path = ROOT_DIR / ".env"
    print("\n📄 Arquivo .env:")
    if env_path.exists():
        print(f"   ✓ Encontrado: {env_path}")
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    # Oculta valores sensíveis
                    if 'KEY' in key or 'SECRET' in key or 'TOKEN' in key:
                        print(f"   • {key.strip()} = ***")
                    else:
                        val = value.strip().strip('"')
                        if len(val) > 40:
                            val = val[:40] + "..."
                        print(f"   • {key.strip()} = {val}")
    else:
        print(f"   ✗ Não encontrado")
    
    # Teste de conexão
    print("\n🔗 Teste de Conexão:")
    if sa_path.exists() and GOOGLE_LIBS_AVAILABLE:
        valid, _, data = validate_service_account(sa_path)
        if valid:
            # Lê SHEET_URL do .env
            sheet_url = None
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('SHEET_URL'):
                            _, _, val = line.partition('=')
                            sheet_url = val.strip().strip('"')
                            break
            
            if sheet_url:
                success, msg = test_service_account_connection(sa_path, sheet_url)
                if success:
                    print(f"   ✓ {msg}")
                else:
                    print(f"   ✗ {msg}")
            else:
                print("   ⚠️  SHEET_URL não configurado no .env")
    else:
        print("   ⚠️  Não foi possível testar (falta service_account.json ou bibliotecas)")
    
    print()
    pause()


# =============================================================================
# MENU PRINCIPAL
# =============================================================================

def main():
    """Menu principal do assistente."""
    while True:
        clear_screen()
        print_header("QUINTESSA EDITAIS - ASSISTENTE DE CONFIGURAÇÃO")
        
        print("""
Escolha uma opção:

  [1] Configurar Service Account (RECOMENDADO)
      → Para distribuição de executáveis

  [2] Configurar OAuth Pessoal (LEGADO)
      → Apenas para desenvolvimento local

  [3] Executar Diagnóstico
      → Verificar status da configuração

  [0] Sair
""")
        
        choice = input("Opção: ").strip()
        
        if choice == "1":
            setup_service_account()
        elif choice == "2":
            setup_oauth_legacy()
        elif choice == "3":
            run_diagnostics()
        elif choice == "0":
            print("\n👋 Até logo!")
            break
        else:
            print("\n⚠️  Opção inválida. Tente novamente.")
            pause()


if __name__ == "__main__":
    main()
