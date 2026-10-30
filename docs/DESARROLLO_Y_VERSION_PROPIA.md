# Desarrollo separado y versión propia

Este documento cubre dos cosas: cómo trabajar en MolChat sin romper MolDesign, y cómo poner una versión propia dentro de MolDesign. El contrato que ambas partes cumplen está en [LLAVE_Y_CERRADURA.md](LLAVE_Y_CERRADURA.md).

## Trabajar en MolChat sin tocar MolDesign

MolDesign ejecuta la copia que tiene fijada. Mientras no la vuelvas a vendorizar, cambiar este repositorio no cambia nada en MolDesign.

1. Trabaja y prueba aquí (una vez, `pip install -e '.[dev]'`):

   ```bash
   python -m pytest
   python -m conformance.runner
   cd ui && npm test && npm run build
   ```

   Algunas pruebas de estructuras necesitan RDKit. El flujo de CI lo instala
   solo en su entorno temporal; para ejecutarlas localmente se puede añadir
   `pip install rdkit`. Las pruebas también comprueban que, si falta, MolChat
   indique que no pudo verificar la estructura. En la integración habitual,
   el host inicia el sidecar con su intérprete de Python: si este incluye
   RDKit, ambos procesos usan esa instalación sin añadir otra al paquete de
   MolChat. Una instalación independiente necesita tener RDKit disponible
   para las funciones de validación y comparación estructural.

2. Haz commits limpios. Sólo lo commiteado se puede integrar.

3. Para probar un cambio dentro de MolDesign sin tocar su copia publicada, vendoriza a una carpeta de prueba desde la raíz de MolDesign:

   ```bash
   python scripts/stage_molchat.py --fuente <esta-carpeta> --write --destino <carpeta-de-prueba>
   ```

   Luego, sólo en desarrollo y sólo en tu máquina, arranca MolDesign con las dos variables (PowerShell):

   ```powershell
   $env:MOLDESIGN_MOLCHAT_DIR = "<carpeta-de-prueba>"
   $env:MOLCHAT_PERMITIR_EXTERNO = "1"
   ```

   Esa carpeta no tiene fijación: MolDesign la acepta porque lo has pedido explícitamente, y el estado del sidecar lo muestra como externo.

4. Cuando el cambio esté listo, vuelve a vendorizar en MolDesign sin `--destino` y confirma el cambio de copia y de fijación en un commit de MolDesign.

## Poner una versión propia dentro de MolDesign

Así puedes modificar MolChat y que MolDesign lo ejecute con tu versión, sin tocar el código de MolDesign.

1. Haz un fork de este repositorio o clónalo. Haz tus cambios en una rama con commits.

2. Comprueba la llave:

   ```bash
   python -m pytest
   python -m conformance.runner
   python scripts/make_manifest.py --write
   ```

3. En tu clon de MolDesign, vendoriza tu commit:

   ```bash
   python scripts/stage_molchat.py --fuente <tu-clon> --write
   python scripts/stage_molchat.py --check
   ```

   La fijación queda con `oficial: false` si `repositorio` no es el repositorio oficial. Eso es lo esperado: MolDesign no pretende que tu versión sea la oficial.

4. Comprueba la integración con MolDesign:

   ```bash
   pytest backend/tests/test_molchat_host_lanzador.py backend/tests/test_protocolo_molchat_e2e.py
   ```

5. Construye MolDesign con tu copia. El estado del sidecar mostrará que no es la versión oficial.

### Licencia

MolChat es GPL-3.0-or-later. Si distribuyes una versión modificada, la licencia te obliga a ofrecer su código fuente a quien la reciba. MolDesign se distribuye bajo PolyForm Noncommercial y no se contagia: se comunican por HTTP y ninguno importa código del otro. Ver `NOTICE.md`.

Esto es ingeniería y procedencia, no asesoría jurídica.
