# Sistema de Cobranza Escolar — Meraki Talent Institute

Sistema en **Python** que lee el archivo de *Cuentas por Cobrar* de cada ciclo
escolar (`.csv` o `.xlsx`), aplica la política **MTI-PRO-ADM-2026-003
(Gestión Integral de Cartera)** y reporta el estado de los pagos, indicando
**a quién avisar y quién es el responsable** de darle seguimiento.

## ¿Por qué Python? (la mejor opción)

Para este caso Python es la opción más efectiva porque:

- Lee indistintamente `.csv` y `.xlsx` y normaliza el formato local
  (`$3.300,00`, fechas `DD/MM/YYYY`, separador `;`).
- Permite codificar las **reglas de la política** (semaforización, responsables,
  escalamiento) en un solo lugar y mantenerlas fácilmente.
- Genera **reportes en Excel** (que ya usa el área) y un **dashboard web**
  amigable para las asistentes/directoras, sin instalar software pesado.

Se entregan **dos formas de uso** sobre el mismo motor:

1. **Dashboard interactivo** (Streamlit): subir archivo, ver semáforo y descargar reporte.
2. **Línea de comandos** (CLI): ideal para automatizar el reporte mensual.

## Semaforización (según la política)

| Semáforo | Antigüedad | Responsable |
|----------|------------|-------------|
| 🟢 Verde | Antes del vencimiento (preventivo) | Asistente Administrativa |
| 🟡 Amarillo | 1 a 30 días | Asistente Administrativa |
| 🟠 Naranja | 31 a 60 días | Directora del Plantel |
| 🔴 Rojo | Más de 60 días | Administración General |

El color se calcula por alumno a partir del **adeudo vencido más antiguo**,
aplicando los pagos al cargo más antiguo primero (FIFO).

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Opción A — Dashboard (recomendado para el día a día)

```bash
streamlit run app.py
```

Se abre en el navegador: sube el archivo, elige la fecha de corte, filtra por
semáforo/nivel y descarga el reporte en Excel.

### Opción B — Línea de comandos (reporte mensual)

```bash
python main.py "Cuentas por Cobrar.csv"
python main.py datos.xlsx --fecha-corte 2026-07-03 --salida reporte.xlsx
python main.py datos.xlsx --color Rojo
```

## Reporte generado

El Excel incluye:

- **Resumen**: indicadores (% de cartera por color, saldo, totales).
- **Todos**: estado de cuenta por alumno con semáforo, saldo, días de atraso,
  responsable y acción sugerida.
- **Rojo / Naranja / Amarillo / Verde**: una hoja por color.
- **A_Contactar**: lista priorizada de alumnos con saldo pendiente.

## Configuración

Todos los parámetros de negocio están en `config.yaml`: umbrales de días,
responsables por color, acciones sugeridas, reglas de escalamiento y el día de
vencimiento por defecto. No es necesario tocar el código para ajustarlos.

## Bitácora de cobranza (MongoDB)

La bitácora permite registrar avisos, medios, resultados y observaciones.
**Se comparte entre todas las computadoras** que usen la misma base en MongoDB Atlas.

### Configurar MongoDB Atlas (una sola vez)

1. Crea cuenta gratis en [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Crea un cluster (M0 Free).
3. En **Database Access**, crea un usuario con contraseña.
4. En **Network Access**, permite tu IP (o `0.0.0.0/0` solo si aceptas acceso amplio).
5. **Connect → Drivers** → copia la cadena de conexión.

### Archivo `.env`

Copia `.env.example` a `.env` y pega tu URI:

```bash
copy .env.example .env
```

```env
MONGODB_URI=mongodb+srv://usuario:contraseña@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

Instala dependencias nuevas:

```bash
pip install -r requirements.txt
```

### Uso de la bitácora en Streamlit

1. **Inicia sesión** con tu usuario y contraseña.
2. Sube el archivo de Cuentas por Cobrar.
3. Pestaña **Registrar aviso**: elige alumno, llena el formulario y guarda.
4. Pestaña **Historial bitácora**: consulta todos los registros del equipo.
5. En **Cartera** verás columnas: Último Aviso, Días Sin Contacto, etc.

### Usuarios del sistema

- Login con **usuario + contraseña** (guardados en MongoDB, contraseñas cifradas con bcrypt).
- Solo **Administración General** puede crear o modificar usuarios (pestaña **Usuarios**).
- El primer administrador se crea automáticamente desde `.env` si no hay usuarios:

```env
ADMIN_USUARIO=admin
ADMIN_NOMBRE=Nombre del administrador
ADMIN_PASSWORD=contraseña_segura
```

Cada registro de bitácora guarda automáticamente el **nombre y rol** del usuario en sesión.

## Despliegue en Streamlit Cloud (recomendado para el equipo)

Publica el sistema en una URL accesible desde cualquier navegador. Las credenciales
quedan **solo en el servidor** (Secrets), no en las computadoras de los usuarios.

### Requisitos previos

1. Repositorio en **GitHub** con este proyecto (sin el archivo `.env`).
2. Cuenta gratuita en [share.streamlit.io](https://share.streamlit.io).
3. Cluster **MongoDB Atlas** con acceso de red **0.0.0.0/0** (Streamlit Cloud no tiene IP fija).

### Paso 1 — Subir el código a GitHub

Asegúrate de que `.env` **no** esté en el repositorio (ya está en `.gitignore`).

```bash
git add .
git commit -m "Preparar despliegue Streamlit Cloud"
git push origin main
```

### Paso 2 — Crear la app en Streamlit Cloud

1. Entra a [share.streamlit.io](https://share.streamlit.io) e inicia sesión con GitHub.
2. Clic en **Create app**.
3. Elige tu repositorio `Sistema_Cobranza_School`.
4. **Main file path:** `app.py`
5. **Branch:** `main` (o la rama que uses).

### Paso 3 — Configurar Secrets

En la app → **Settings** → **Secrets**, pega el contenido de
`.streamlit/secrets.toml.example` con tus valores reales:

```toml
MONGODB_URI = "mongodb+srv://usuario:contraseña@cluster.mongodb.net/?retryWrites=true&w=majority"
MONGODB_DB = "meraki_cobranza"
ADMIN_USUARIO = "admin"
ADMIN_NOMBRE = "Administrador General"
ADMIN_PASSWORD = "tu_contraseña_segura"
```

Guarda y espera a que la app se **reinicie**.

### Paso 4 — Probar

1. Abre la URL que te da Streamlit (ej. `https://tu-app.streamlit.app`).
2. Inicia sesión con el usuario admin.
3. Sube un archivo de Cuentas por Cobrar y verifica la bitácora.

### MongoDB Atlas — acceso de red

En Atlas → **Network Access** → **Add IP Address** → **Allow Access from Anywhere**
(`0.0.0.0/0`). Sin esto, Streamlit Cloud no podrá conectar.

### Desarrollo local con Secrets (opcional)

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# Edita secrets.toml con tus credenciales
streamlit run app.py
```

### Dominio propio (opcional)

En Streamlit Cloud → **Settings** → **General** puedes configurar un subdominio
personalizado si tu plan lo permite, o usar la URL `.streamlit.app` que ya incluye HTTPS.

---

## Ejecutable para Windows (.exe)

Puedes generar un programa que **no requiere instalar Python** en cada computadora.

### Generar el ejecutable (solo en tu PC de desarrollo)

1. Instala Python 3.10 o superior.
2. Doble clic en **`build_exe.bat`** o ejecuta en terminal:

```bash
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller SistemaCobranza.spec --noconfirm --clean
```

3. El resultado queda en:

```
dist\SistemaCobranzaMeraki\
  SistemaCobranzaMeraki.exe   ← abrir este archivo
  (librerías y dependencias)
```

### Distribuir a otras computadoras

1. Copia **toda la carpeta** `SistemaCobranzaMeraki` (no solo el .exe).
2. En esa carpeta, crea o edita el archivo **`.env`** con tu `MONGODB_URI` y usuarios admin.
3. Ejecuta **`SistemaCobranzaMeraki.exe`** → se abrirá el navegador con el sistema.
4. Para cerrar: cierra la ventana negra (consola) o presiona `Ctrl+C`.

### Requisitos en cada PC

| Requisito | Detalle |
|-----------|---------|
| Windows 10/11 | 64 bits recomendado |
| Internet | Necesario para MongoDB Atlas |
| Navegador | Chrome, Edge o Firefox |
| Python | **No** hace falta instalarlo |

### Notas

- El ejecutable pesa ~300–500 MB (incluye Python y librerías).
- El antivirus puede pedir confirmación la primera vez (común con PyInstaller).
- Todos los equipos comparten la misma bitácora si usan el **mismo `.env`** (misma base MongoDB).

## Estructura

```
├── app.py               # Dashboard Streamlit (+ bitácora)
├── .streamlit/
│   ├── config.toml      # Tema y opciones de la app
│   └── secrets.toml.example  # Plantilla para Streamlit Cloud
├── launcher.py          # Entrada del ejecutable Windows
├── build_exe.bat        # Script para generar el .exe
├── SistemaCobranza.spec # Configuración PyInstaller
├── main.py              # CLI / reporte mensual
├── config.yaml          # Reglas de la política (editable)
├── .env.example         # Plantilla de conexión MongoDB
├── requirements.txt
└── cobranza/
    ├── config.py        # Carga de configuración
    ├── cargador.py      # Lectura y normalización (csv/xlsx)
    ├── analisis.py      # Semaforización por alumno + indicadores
    ├── bitacora.py      # Bitácora en MongoDB Atlas
    ├── mongodb.py       # Conexión compartida a MongoDB
    ├── usuarios.py      # Login y gestión de usuarios
    └── reporte.py       # Exportación a Excel con formato
```

## Notas sobre los datos

- Se ignoran los movimientos marcados como **Cancelado**.
- El **saldo** se calcula como `Σ Cargos − Σ Abonos` por alumno (matrícula + ciclo).
- El vencimiento se reconstruye a partir del periodo del concepto
  (ej. "septiembre - 2025") porque el archivo real trae años de vencimiento
  inconsistentes; así el cálculo de atraso es confiable.

## Siguientes pasos sugeridos (opcionales)

- Agregar columna de **teléfono/correo del tutor** al archivo para generar los
  mensajes de aviso (WhatsApp/correo) automáticamente.
- Alertas cuando un **compromiso de pago** vence sin liquidar el adeudo.
