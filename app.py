import os
import functools
from flask import Flask, request, Response
import oracledb

app = Flask(__name__)

BASIC_AUTH_USER = os.environ["BASIC_AUTH_USER"]
BASIC_AUTH_PASSWORD = os.environ["BASIC_AUTH_PASSWORD"]

DB_USER = os.environ["ORACLE_USER"]
DB_PASSWORD = os.environ["ORACLE_PASSWORD"]
DB_HOST = os.environ["ORACLE_HOST"]
DB_PORT = os.environ.get("ORACLE_PORT", "1521")
DB_SERVICE = os.environ["ORACLE_SERVICE"]


def require_basic_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != BASIC_AUTH_USER or auth.password != BASIC_AUTH_PASSWORD:
            return Response("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Login"'})
        return f(*args, **kwargs)
    return wrapper


@app.route("/execute", methods=["POST"])
@require_basic_auth
def execute():
    body = request.get_data(as_text=True)
    statements = [line.strip() for line in body.splitlines() if line.strip()]
    if not statements:
        return {"error": "no statements"}, 400

    dsn = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"
    try:
        with oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn) as conn:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            conn.commit()
    except oracledb.DatabaseError as e:
        return {"error": str(e)}, 500

    return {"executed": len(statements)}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
