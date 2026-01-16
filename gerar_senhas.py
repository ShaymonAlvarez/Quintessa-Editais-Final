import hashlib
import os
import binascii

def gerar_hash_seguro(senha):
    """
    Gera um hash seguro usando PBKDF2 (padrão nativo do Python).
    Não requer bibliotecas externas.
    """
    # 1. Cria um "sal" aleatório de 16 bytes
    salt = os.urandom(16)
    
    # 2. Gera o hash usando SHA256 e 100.000 iterações (Padrão seguro)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, 100000)
    
    # 3. Retorna no formato: salt_hex$hash_hex
    # (Precisamos guardar o sal junto para conseguir verificar a senha depois)
    return f"{binascii.hexlify(salt).decode('ascii')}${binascii.hexlify(pwd_hash).decode('ascii')}"

def main():
    print("==========================================")
    print("   GERADOR DE SENHAS (SEM DEPENDÊNCIAS)")
    print("==========================================")
    
    email = input("Digite o e-mail do usuário: ")
    senha = input(f"Digite a senha para '{email}': ")
    
    if not senha:
        print("\n[ERRO] A senha não pode ser vazia.")
        return

    # Gera o hash
    hash_final = gerar_hash_seguro(senha)
    
    print("\n" + "="*50)
    print("SUCESSO! Copie o bloco abaixo para o seu users.json no Gist:")
    print("="*50)
    print("    {")
    print(f'      "email": "{email}",')
    print(f'      "password_hash": "{hash_final}"')
    print("    },")
    print("="*50)
    
    input("\nPressione ENTER para sair...")

if __name__ == "__main__":
    main()