# Oracle REST API

Minimaler Python-Service der SQL INSERT-Statements per REST-Endpoint entgegennimmt und auf eine Oracle-Datenbank anwendet. Geschützt via HTTP Basic Auth.

## Funktionsweise

```
POST /execute  (Basic Auth)
Content-Type: text/plain

INSERT INTO orders (id, name) VALUES (1, 'foo');
INSERT INTO orders (id, name) VALUES (2, 'bar');
```

Jede nicht-leere Zeile wird als einzelnes SQL-Statement ausgeführt. Alle Statements laufen in einer Transaktion – bei einem Fehler wird nichts committed.

---

## Voraussetzungen

- Python 3.12+
- Zugang zu einer Oracle-Instanz (lokal oder remote)
- Docker (für Container-Build)
- `kubectl` + OpenShift-Cluster (für Deployment)
- `helm` 3.x (für Helm-Deployment)

---

## Lokales Testen

### 1. Python direkt

```bash
pip install -r requirements.txt

export ORACLE_USER=myuser
export ORACLE_PASSWORD=mypassword
export ORACLE_HOST=localhost
export ORACLE_PORT=1521
export ORACLE_SERVICE=FREEPDB1
export BASIC_AUTH_USER=admin
export BASIC_AUTH_PASSWORD=secret

python app.py
```

Der Server startet auf `http://localhost:8080`.

### 2. Lokale Oracle-Instanz mit Docker

Oracle Free Edition (kostenlos, kein Account nötig):

```bash
docker run -d \
  --name oracle-free \
  -p 1521:1521 \
  -e ORACLE_PASSWORD=mypassword \
  container-registry.oracle.com/database/free:latest
```

Warten bis die Datenbank bereit ist (~60s):

```bash
docker logs -f oracle-free | grep -m1 "DATABASE IS READY"
```

Verbindungsdaten für die App:

```
ORACLE_USER=system
ORACLE_PASSWORD=mypassword
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
```

### 3. Endpoint aufrufen

```bash
# Einzelnes Statement
curl -u admin:secret \
  -X POST http://localhost:8080/execute \
  -H "Content-Type: text/plain" \
  -d "INSERT INTO test_table (id, val) VALUES (1, 'hello')"

# Mehrere Statements aus Datei
curl -u admin:secret \
  -X POST http://localhost:8080/execute \
  -H "Content-Type: text/plain" \
  --data-binary @inserts.sql
```

Beispiel `inserts.sql`:

```sql
INSERT INTO test_table (id, val) VALUES (1, 'alpha');
INSERT INTO test_table (id, val) VALUES (2, 'beta');
INSERT INTO test_table (id, val) VALUES (3, 'gamma');
```

Erfolgreiche Antwort:

```json
{"executed": 3}
```

Fehler-Antwort (z.B. Tabelle nicht vorhanden):

```json
{"error": "ORA-00942: table or view does not exist"}
```

### 4. Auth-Fehler testen

```bash
# Kein Auth → 401
curl -v -X POST http://localhost:8080/execute -d "INSERT ..."

# Falsches Passwort → 401
curl -u admin:wrong -X POST http://localhost:8080/execute -d "INSERT ..."
```

---

## Docker

### Build

```bash
docker build -t oracle-rest-api:latest .
```

### Run

```bash
docker run -p 8080:8080 \
  -e ORACLE_USER=myuser \
  -e ORACLE_PASSWORD=mypassword \
  -e ORACLE_HOST=host.docker.internal \
  -e ORACLE_PORT=1521 \
  -e ORACLE_SERVICE=FREEPDB1 \
  -e BASIC_AUTH_USER=admin \
  -e BASIC_AUTH_PASSWORD=secret \
  oracle-rest-api:latest
```

> `host.docker.internal` verweist vom Container auf das Host-System (macOS/Windows). Unter Linux stattdessen `172.17.0.1` oder die Host-IP verwenden.

### Push in Registry

```bash
docker tag oracle-rest-api:latest your-registry.example.com/oracle-rest-api:1.0.0
docker push your-registry.example.com/oracle-rest-api:1.0.0
```

---

## Kubernetes / OpenShift – Plain Manifeste

### Secrets anlegen

Die beiden Secrets müssen vor dem Deployment existieren. Werte müssen base64-kodiert sein (`echo -n 'wert' | base64`).

```bash
kubectl create secret generic oracle-credentials \
  --from-literal=ORACLE_USER=myuser \
  --from-literal=ORACLE_PASSWORD=mypassword \
  --from-literal=ORACLE_HOST=oracle.example.com \
  --from-literal=ORACLE_PORT=1521 \
  --from-literal=ORACLE_SERVICE=MYSERVICE

kubectl create secret generic oracle-rest-api-auth \
  --from-literal=BASIC_AUTH_USER=admin \
  --from-literal=BASIC_AUTH_PASSWORD=secret
```

Alternativ über die Beispieldatei (nach Befüllen der Werte):

```bash
kubectl apply -f k8s/secrets.example.yaml
```

### Deployment

```bash
# Image in deployment.yaml anpassen:
# image: your-registry.example.com/oracle-rest-api:1.0.0

kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## Helm

### Struktur

```
helm/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    └── route.yaml          # OpenShift Route mit Edge TLS
```

### Konfigurierbare Werte (`values.yaml`)

| Wert | Beschreibung | Default |
|------|-------------|---------|
| `image.registry` | Container-Registry | `your-registry.example.com` |
| `image.repository` | Image-Name | `oracle-rest-api` |
| `image.tag` | Image-Tag | `latest` |
| `secrets.oracle` | Name des Oracle-Secrets | `oracle-credentials` |
| `secrets.auth` | Name des Basic-Auth-Secrets | `oracle-rest-api-auth` |
| `route.host` | Hostname der OpenShift Route | `""` (auto) |
| `replicaCount` | Anzahl Replicas | `1` |

### Install / Upgrade

```bash
# Minimales Deployment – OpenShift generiert den Hostnamen automatisch
helm install my-api ./helm \
  --set image.registry=your-registry.example.com \
  --set image.tag=1.0.0

# Mit explizitem Hostnamen für die Route
helm install my-api ./helm \
  --set image.registry=your-registry.example.com \
  --set image.tag=1.0.0 \
  --set route.host=api.apps.cluster.example.com

# Eigene Secret-Namen
helm install my-api ./helm \
  --set secrets.oracle=prod-oracle-secret \
  --set secrets.auth=prod-auth-secret

# Upgrade nach Image-Update
helm upgrade my-api ./helm --set image.tag=1.1.0

# Deinstallieren
helm uninstall my-api
```

### Dry-Run (Manifeste prüfen ohne Deployment)

```bash
helm template my-api ./helm \
  --set image.registry=your-registry.example.com \
  --set image.tag=1.0.0
```

---

## OpenShift Route

Die Route ist mit **Edge Termination** konfiguriert:

- TLS wird am OpenShift Router terminiert
- Backend-Kommunikation läuft intern über HTTP
- HTTP-Requests werden automatisch zu HTTPS weitergeleitet

Wird `route.host` leer gelassen, generiert OpenShift den Hostnamen nach dem Schema:

```
<release-name>-<namespace>.apps.<cluster-domain>
```

Den tatsächlichen Hostnamen nach dem Deployment auslesen:

```bash
oc get route my-api -o jsonpath='{.spec.host}'
```

---

## Umgebungsvariablen

| Variable | Quelle | Beschreibung |
|----------|--------|-------------|
| `ORACLE_USER` | Secret `oracle-credentials` | DB-Benutzer |
| `ORACLE_PASSWORD` | Secret `oracle-credentials` | DB-Passwort |
| `ORACLE_HOST` | Secret `oracle-credentials` | DB-Hostname |
| `ORACLE_PORT` | Secret `oracle-credentials` | DB-Port (default: 1521) |
| `ORACLE_SERVICE` | Secret `oracle-credentials` | Oracle Service Name |
| `BASIC_AUTH_USER` | Secret `oracle-rest-api-auth` | API-Benutzername |
| `BASIC_AUTH_PASSWORD` | Secret `oracle-rest-api-auth` | API-Passwort |
