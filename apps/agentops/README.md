# AgentOps: el restaurante bajo control

Panel para explicar el ciclo de vida de un cambio en el restaurante. Es un
complemento docente separado: no sustituye al frontend Streamlit ni modifica
los agentes del restaurante.

## Preparación

Necesitas Python 3.13 o superior y [uv](https://docs.astral.sh/uv/). Desde la
raíz del repositorio:

```powershell
uv sync --frozen --project agents\cashier\src\cashier_agent
uv run --frozen --project agents\cashier\src\cashier_agent python apps\agentops\server.py
```

En Windows también puedes ejecutar los comandos desde PowerShell tal como se
indican. Abre **http://127.0.0.1:8765/**. No necesita Docker, Foundry,
credenciales ni llamadas a modelos. El servidor escucha solo en el equipo
local; no lo expongas a Internet ni lo uses como servicio multiusuario.
Para terminarlo, pulsa `Ctrl+C` en la terminal.

En el equipo de preparación, si ya existe `.venv-classroom-tools`, también
puedes arrancar sin `uv`:

```powershell
.\.venv-classroom-tools\Scripts\python.exe apps\agentops\server.py
```

Ese entorno local no está versionado y contiene las dependencias necesarias
para los tests de este panel, pero no reproduce el lock completo del proyecto.

Para comprobar automáticamente el recorrido:

```powershell
uv run --frozen --project agents\cashier\src\cashier_agent python apps\agentops\server.py --self-test
```

Este comando comprueba que la versión original pasa las pruebas y que la
regresión hace fallar la prueba concreta de cantidades; un error de
instalación o de recogida de pruebas no cuenta como regresión detectada.
El workflow `agentops-classroom.yml` ejecuta la misma comprobación en GitHub
Actions al cambiar este panel o las dependencias de caja.

## Guion para proyectar (15–20 min)

1. **Arquitectura.** Señala frontend → BFF → camarero → cocina/caja y explica
   MCP, A2A y responsabilidades. El panel no arranca esos servicios.
2. **Hipótesis.** En caja, cada línea tiene precio y cantidad. Pregunta si se
   puede simplificar el cálculo omitiendo la cantidad.
3. **Regresión.** Selecciona B y pulsa «Ejecutar pruebas». Abre la salida de
   pytest: la prueba existente de varias cantidades falla y el gate bloquea la
   aprobación. La modificación se hace solo en una copia temporal que se
   elimina al terminar; no se cambia código del repositorio.
4. **Versión original.** Selecciona A y ejecuta de nuevo. Enseña la salida de
   las pruebas reales y que el hash SHA-256 identifica el código original
   copiado. Las pruebas no demuestran que un sistema entero sea correcto.
5. **Humano.** Aprueba o rechaza. La aprobación es una simulación local, no una
   identidad ni un environment protegido en GitHub.
6. **Canary.** Tras aprobar, lanza 20 solicitudes sintéticas; 4 van a la
   candidata. Inyecta el fallo: 2 de 4 son errores. Pregunta qué umbral
   aplicarían y pulsa rollback. No se envía tráfico ni se despliega nada.
7. **Salto a producción.** Enseña Actions del repositorio: existen workflows de
   imágenes por SHA y E2E con dobles. Compara con lo que faltaría: protección
   de ramas, revisión humana verificable, datasets de evaluación de agentes,
   gateway de modelos, métricas reales y política de despliegue y rollback.

El «agente de desarrollo» es una hipótesis didáctica: este panel no ejecuta un
agente de programación. El defecto se inyecta con una sustitución fija en una
copia temporal. Si cambia el código original, el panel falla explícitamente
hasta que se adapte el ejemplo. No se evalúa el modelo, la seguridad integral,
el comportamiento de todos los servicios ni el estado de un despliegue.

Los tests pueden tardar al arrancar. Si fallan por dependencias o por un error
de recopilación, enseña la salida y no presentes ese fallo como una regresión
de producto. El estado de la demo se pierde al recargar la página.
