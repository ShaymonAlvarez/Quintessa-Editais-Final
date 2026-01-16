import uvicorn
import os
import sys

# Garante que a raiz do projeto esteja no caminho de importação
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa a aplicação do backend
from backend.api import app

if __name__ == "__main__":
    # Inicia o servidor. 
    # reload=False é importante para produção/exe
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")