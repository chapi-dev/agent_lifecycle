# Healthcare AgentOps · Centro de control

Demo docente de **administración sanitaria**, con expedientes sintéticos y
cuatro componentes deterministas: recepción, documentación, coordinación y
auditoría. No utiliza modelos ni agentes autónomos basados en LLM. No procesa
datos personales, realiza acciones externas, agenda citas, diagnostica ni
presta atención médica.

## Ejecutar en local

Desde la raíz del repositorio:

```powershell
python apps\healthcare\server.py
```

Abre <http://127.0.0.1:8765/>. Para comprobar los tests:

```powershell
python -m unittest discover -s apps\healthcare -p "test_*.py" -v
```

Solo usa la biblioteca estándar de Python. `HOST` y `PORT` permiten ajustar
la dirección y el puerto, respectivamente; por defecto escucha únicamente en
el equipo local. Exponerlo en una red no lo convierte en un sistema sanitario
real: carece de autenticación y no debe recibir datos reales.

## Guion docente

1. En **Observar**, elige «Falta la derivación» y ejecuta el recorrido.
   Enseña la secuencia real de componentes y el resultado «Pendiente».
2. Selecciona la **regresión de ejemplo** y vuelve a ejecutar: verás que la
   propuesta sería incorrecta. Es una rama fija del código para el aula; no
   cambia ninguna configuración de producción.
3. Ejecuta la evaluación de la regresión: uno de los cuatro casos debe fallar,
   y la interfaz bloquea la aprobación. Explica los resultados esperado y
   observado.
4. Selecciona la **versión estable** y evalúala: los cuatro casos pasan. La
   ausencia de fallos en estos cuatro casos no demuestra que un sistema sea
   seguro.
5. Aprueba la simulación, lanza 20 solicitudes sintéticas, inyecta el fallo y
   vuelve atrás. Se simulan 16 solicitudes estables, 4 candidatas y 2 errores
   candidatos. No se envía tráfico, no se cambian revisiones y no se modifica
   ningún recurso de Azure.
6. Contrasta este ejemplo con un pipeline real: PR, tests automáticos, revisión
   identificada, modelos y evaluaciones de herramientas si hay LLM, artefactos
   inmutables, gateway, observabilidad y despliegue controlado.

## Qué es real y qué no

El servidor ejecuta reglas y la evaluación sobre cuatro casos; las trazas
mostradas se construyen durante esa ejecución. No hay un framework de agentes,
modelo, gateway, datos sanitarios ni integración clínica. La revisión humana,
el canary y el rollback son interacciones de la página sin identidad ni
efectos externos. El workflow de GitHub ejecuta los tests unitarios reales.

La app no almacena los casos ni tiene un formulario de texto libre. Los
resultados operativos y la aprobación se pierden al recargar la página. El
servidor no registra peticiones, pero la plataforma donde se aloje puede
generar sus propios logs técnicos.
