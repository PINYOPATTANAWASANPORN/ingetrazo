# AI Bridge — modelar con Claude (MCP)

IngeTrazo puede ser dirigido por un agente de IA (Claude Code, Claude
Desktop) mediante el [Model Context Protocol](https://modelcontextprotocol.io):
el agente dibuja, consulta y **ve** el modelo en vivo — y cada acción suya
es un paso de undo transaccional (si su código falla, el documento se
revierte entero; el guard de hermeticidad valida sus recetas).

## Uso

1. En IngeTrazo: pestaña **IA** de la barra lateral ▸ sección **Puente IA
   (MCP)** ▸ **Encender puente** (o **Extensiones ▸ Puente IA (MCP)**, que
   abre esa sección y lo enciende) — arranca un servidor local (solo
   127.0.0.1, puerto 4763; `INGETRAZO_AI_PORT` lo cambia). **Detener
   puente** lo apaga.
2. Al encenderlo, la sección muestra, con un botón Copiar, las líneas exactas para
   tu sistema (botón **Copiar**). No hace falta tener Python instalado: el
   paquete lleva el servidor MCP.

   | Instalación | Comando del servidor MCP |
   |---|---|
   | Windows (instalador o zip) | `C:\Program Files\IngeTrazo\ingetrazo-mcp.exe` |
   | Linux AppImage / tarball / Flatpak / snap | `<ejecutable de IngeTrazo> --mcp` |
   | Desde el repositorio | `python3 /ruta/a/app/scripts/ingetrazo_mcp.py` |

   **Claude Code** (en una terminal):

       claude mcp add ingetrazo -- "C:\Program Files\IngeTrazo\ingetrazo-mcp.exe"

   **Claude Desktop**: pega esto en su archivo de configuración
   (`%APPDATA%\Claude\claude_desktop_config.json` en Windows,
   `~/.config/Claude/claude_desktop_config.json` en Linux) y reinicia
   Claude Desktop:

       {
         "mcpServers": {
           "ingetrazo": {
             "command": "C:\\Program Files\\IngeTrazo\\ingetrazo-mcp.exe",
             "args": []
           }
         }
       }

   Si Claude no responde: comprueba que IngeTrazo sigue abierto con el
   puente encendido (la sección Puente IA (MCP) dice «Escuchando en…»),
   que la ruta del comando existe, y en Claude Desktop que el servidor
   aparece en Configuración ▸ Desarrollador ▸ MCP sin error.
3. Pídele cosas: *"dibuja una casita de 6×4 m con techo a dos aguas,
   agrúpala y píntala de ladrillo; muéstrame cómo quedó"*.

### El agente dentro de un contenedor (Docker, WSL2)

El puente escucha **solo en `127.0.0.1`** de la máquina donde corre
IngeTrazo, y así se queda: no tiene contraseña y `run_python` ejecuta
código dentro de la aplicación, de modo que abrirlo a la red dejaría el
modelo (y el equipo) a merced de cualquiera en ella.

- **IngeTrazo dentro de WSL2** (AppImage o `.tar.gz` con WSLg) y el
  contenedor con `--network host`: funciona tal cual, porque comparten
  `127.0.0.1`.
- **En cualquier otro caso**, lleva el puerto hasta el agente con un túnel
  que tú controlas (`ssh -L 4763:127.0.0.1:4763 usuario@equipo`, `socat`…)
  y dile al cliente MCP dónde está el otro extremo:

      INGETRAZO_AI_HOST=host.docker.internal INGETRAZO_AI_PORT=4763 \
          python3 /ruta/a/app/scripts/ingetrazo_mcp.py

  `INGETRAZO_AI_HOST` (por defecto `127.0.0.1`) solo cambia a dónde se
  conecta el cliente; el puente no deja de escuchar únicamente en local.

## Herramientas expuestas

| Tool | Qué hace |
|---|---|
| `run_python` | Ejecuta Python sobre el documento vivo (scope: `scene`, `mesh`, `selection`, `groups`, `bim`, `QVector3D`… y los constructores `revolve(perfil)` / `extrude(contorno, z0, z1)`: una línea → un grupo sólido, suave y orientado). Un undo por llamada; rollback total si falla. |
| `query_model` | Conteos, nombres de grupos/componentes, materiales, capas, bounds. |
| `get_document_context` | El contexto acotado y paginado para empezar: revisión de contenido/vista, unidades, etiqueta activa, selección, capas y el árbol de grupos/componentes. El cursor deja de ser válido si cambia el documento o la selección. |
| `find_entities` | Busca grupos/componentes por fragmento de nombre, ID estable o etiqueta; el cursor se invalida solo si cambia el contenido. |
| `get_entities` | Detalle de los IDs estables de grupos/componentes: estado, etiqueta, material, transformación y metadatos. Caras, aristas y vértices no se exponen como IDs duraderos porque una operación topológica puede reconstruirlos. |
| `get_capabilities` | Contrato de la puerta IA: qué identificadores son estables y qué funciones de escritura, preview o multiagente están disponibles. |
| `create_task` | Convierte una intención corta en un contrato fijado a la revisión actual: alcance automático o explícito, objetivo, restricciones, supuestos, criterios de aceptación y un plan pequeño de roles. No modifica el modelo. |
| `get_task` | Devuelve el contrato, estado y resultado de la tarea; avisa si una edición posterior dejó obsoleta su revisión base. |
| `propose_actions` | Propone, sin modificar el documento, cambios tipados de nombre, visibilidad, bloqueo, etiqueta, material o transformación, además de crear cajas y cilindros como grupos/componentes de nivel superior. Devuelve valores y límites antes/después. |
| `preview_changes` / `validate_changes` | Recupera y vuelve a validar una propuesta contra la revisión viva del documento. |
| `commit_changes` / `discard_changes` | Solicita que la app muestre Aplicar/Descartar, o descarta la propuesta. El cliente MCP nunca puede saltarse la aprobación humana. |
| `screenshot` | Renderiza el viewport real — el agente mira e itera. |
| `undo` / `redo` | La historia de siempre. |

Sin el puente encendido, las tools responden con el aviso de cómo
encenderlo. El servidor acepta un cliente a la vez y nunca escucha fuera
de localhost.

## Asistente IA (dentro de la app)

Para el usuario que no usa Claude Code: la pestaña **IA** de la barra
lateral (Ctrl+Shift+A la trae al frente, aunque esté oculta) es un chat
DENTRO de IngeTrazo. Pega tu clave API — el
proveedor se detecta solo por el prefijo, la convención de IngePresupuestos:

| Prefijo | Proveedor | Modelo por defecto |
|---|---|---|
| `sk-ant-` | Anthropic | claude-sonnet-5 |
| `gsk_` | Groq (gratis) | llama-3.3-70b-versatile |
| `sk-or-` | OpenRouter | anthropic/claude-sonnet-5 |
| `AIza` | Gemini | gemini-2.5-flash |
| `sk-` | OpenAI | gpt-4o |
| *(vacía)* | Ollama local | llama3.2 |

Escribe qué quieres. Para renombrar, mostrar/ocultar, bloquear, asignar una
etiqueta o material, y mover/girar/escalar grupos o componentes de nivel
superior, el asistente devuelve acciones tipadas y muestra los valores antes
y después. El modelo no cambia hasta pulsar **Aplicar cambios**; **Descartar**
no deja ningún cambio y una revisión obsoleta se rechaza. Aplicar registra el
conjunto como un solo paso de Deshacer. La creación de geometría y las
operaciones aún no tipadas conservan temporalmente las recetas Python
transaccionales. Estas recetas están apagadas por defecto y solo se aceptan si
el usuario activa **Permitir recetas Python avanzadas para esta sesión**. La
preferencia no se guarda. Con proveedores con visión, el asistente recibe
capturas del viewport para revisar lo que construyó.

Antes de cada turno el asistente recibe un resumen pequeño del documento
abierto (selección, unidades, etiqueta activa y los primeros grupos). Así un
pedido corto puede referirse a lo que ya está en pantalla sin que el usuario
tenga que enumerarlo. El resumen nunca reemplaza el árbol entero: un cliente
MCP usa las herramientas paginadas cuando necesita más detalle.

Un cliente MCP puede empezar con una frase corta mediante `create_task`. Con
`scope: auto`, IngeTrazo usa primero los grupos/componentes seleccionados,
después el grupo abierto y finalmente el modelo visible. Los IDs resueltos
quedan fijados en la tarea: `propose_actions` rechaza cualquier objeto fuera
de ese alcance, aunque el agente intente ampliar silenciosamente el trabajo.

La caja del Asistente ofrece los mismos datos como controles compactos:
**alcance**, **objetivo**, **Actuar (deshacer)** o **Solo análisis**, más una
línea de supuestos visibles separada por punto y coma. El contrato acompaña
automáticamente cada turno. Solo análisis rechaza cualquier receta Python
o propuesta tipada devuelta por el proveedor. Actuar usa vista previa tipada
para las acciones admitidas y mantiene la ruta de recetas como compatibilidad
para edición de geometría aún no cubierta. `create_box` y `create_cylinder`
permiten crear masas básicas mediante la misma vista previa sin recurrir a
Python.

El botón **Memoria** abre los hechos duraderos del proyecto, uno por línea.
Se guardan dentro del `.igz`, la edición participa en Deshacer/Rehacer y cada
tarea nueva recibe una copia fija bajo `project_memory`. Esta memoria tiene
límites de tamaño y solo la cambia el usuario desde la interfaz; una respuesta
del chat o una llamada `create_task` no puede convertir una inferencia en una
preferencia permanente sin que el usuario la vea.

### Modelar desde una foto

Con el botón **Foto…** adjuntas la imagen de un objeto (una fuente, un
mueble, una fachada) y el asistente la interpreta y lo recrea por partes,
cada una como grupo con nombre, comparando sus capturas contra la foto.
Dale las medidas reales en el mensaje ("la taza mide 4 m de diámetro, el
alto total 2,30") — una foto no trae dimensiones, y lo que el asistente
estime del ojo lo declara como supuesto para que lo corrijas. La foto se
reescala a 1280 px y viaja como JPEG solo en ese mensaje. Necesita un
proveedor con visión (Anthropic, OpenAI, Gemini, OpenRouter).
