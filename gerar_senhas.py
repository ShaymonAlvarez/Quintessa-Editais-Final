from passlib.context import CryptContext

# Usar argon2 em vez de bcrypt (mais compatível e moderno)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def gerar_hash_seguro(senha):
    """
    Gera um hash seguro usando argon2.
    """
    return pwd_context.hash(senha)

def main():
    print("==========================================")
    print("   GERADOR DE SENHAS (ARGON2)")
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