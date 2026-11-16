# Bar AgentOps · Clase interactiva

Demo docente de un bar ficticio. La fachada y el plano proceden de la vista
original del restaurante; la conversación de esa vista es simulada. El botón
**Ejecutar pedido** llama a la API, que calcula el recorrido con reglas
deterministas de camarero, barra, cocina y caja. La animación representa los
eventos devueltos; no mide su duración ni ejecuta acciones externas.

## Ejecutar

Desde la raíz del repositorio:

```powershell
python apps\healthcare\server.py
```

Abre <http://127.0.0.1:8765/>. La puerta requiere un nombre ficticio; en la
barra superior está el dashboard. Para comprobar los tests:

```powershell
python -m pip install -r apps\healthcare\requirements.txt
python -m unittest discover -s apps\healthcare -p "test_*.py" -v
```

## Guion de clase

1. Entra en el bar y ejecuta el pedido con agua con gas agotada. La barra
   estable detecta que falta stock y el pedido queda retenido.
2. Abre el dashboard y elige **Cambio defectuoso**. La candidata omite la
   comprobación del stock de bebida. Es una rama fija del código para el aula.
3. Pulsa **Ver esta versión en el bar**: la barra se ilumina en rojo al
   aceptar la bebida agotada. El mismo caso y la versión se conservan en
   `sessionStorage` del navegador; no se modifican otros usuarios ni Azure.
4. Vuelve al dashboard y ejecuta la evaluación: el gate detecta el caso
   incorrecto y bloquea la aprobación simulada. Cambia a la estable y
   comprueba que los cuatro casos pasan. Cuatro casos no prueban seguridad.
5. Simula aprobación, canary, un fallo y rollback. Son interacciones locales:
   no despliegan revisiones, no envían tráfico y no cambian GitHub ni Azure.

La explicación opcional utiliza un LLM real, solo con los casos predefinidos;
no dirige a los roles ni altera las reglas o el gate. El usuario debe poner la
clave de demo en la página, nunca en una URL. Para probarlo en local:

```powershell
az login
$env:HEALTHOPS_MODEL_ENDPOINT = 'https://<tu-recurso>.cognitiveservices.azure.com'
$env:HEALTHOPS_MODEL_DEPLOYMENT = '<tu-deployment>'
$env:HEALTHOPS_DEMO_TOKEN = '<clave-larga-aleatoria-para-la-demo>'
python apps\healthcare\server.py
```

En Azure se usa identidad administrada. La página es pública y solo la llamada
al modelo requiere clave compartida. El límite de 20 intentos por hora es por
proceso y se reinicia; no sustituye autenticación individual ni un límite de
gasto. El modelo puede procesar los datos ficticios fuera de la región.

No hay un framework de agentes conectado a este recorrido ni un AI gateway.
El proyecto conserva el backend multiagente original del restaurante por
separado; esta aplicación no lo despliega. No se sirven pedidos ni se cobra.
