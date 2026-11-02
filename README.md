# Verificación de EPP – Laboratorios de Biotecnología UNEMI

Aplicativo web para registro y verificación de EPP mediante visión artificial.

## Requisitos
- Python 3.12 o superior
- PostgreSQL 16 o superior (con pgAdmin)
- Git

## Instalación
1. Clonar el repositorio:
   ```
   git clone https://github.com/KarlaSantillan/verificacion-epp.git
   cd verificacion-epp
   ```
2. Crear y activar el entorno virtual:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```
4. En pgAdmin (Query Tool), ejecutar por separado:
   ```sql
   CREATE USER epp_user WITH PASSWORD 'su_clave';
   CREATE DATABASE epp_db OWNER epp_user ENCODING 'UTF8';
   ```
5. Copiar `.env.example` como `.env` y completar la contraseña de la base de datos.
6. Verificar la conexión:
   ```
   python manage.py check --database default
   ```
7. Ejecutar el servidor:
   ```
   python manage.py runserver
   ```